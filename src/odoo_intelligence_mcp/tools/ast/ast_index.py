from typing import Any

from ...core.env import load_env_config
from ...utils.docker_utils import DockerClientManager


async def build_ast_index(roots: list[str] | None = None) -> dict[str, Any]:
    config = load_env_config()
    container = config.web_container
    if roots is None or not roots:
        roots = [p.strip() for p in config.addons_path.split(",") if p.strip()]

    # Python code to run inside the web container to build a lightweight AST index
    import json as _json  # local only for string building

    roots_json = _json.dumps(roots)
    header = "import ast, os, json\n" + "roots = " + roots_json + "\n"
    # noinspection SpellCheckingInspection
    body = """

def is_model_base(base):
    try:
        # matches: models.Model
        return isinstance(base, ast.Attribute) and getattr(base.value, 'id', None) == 'models' and base.attr == 'Model'
    except Exception:
        return False

def str_const(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None

def list_of_str(node):
    if isinstance(node, (ast.List, ast.Tuple)):
        vals = []
        for elt in node.elts:
            s = str_const(elt)
            if s is not None:
                vals.append(s)
        return vals
    s = str_const(node)
    return [s] if s is not None else []

def dict_of_str(node):
    if isinstance(node, ast.Dict):
        out = {}
        for k, v in zip(node.keys, node.values):
            ks = str_const(k)
            vs = str_const(v)
            if ks is not None and vs is not None:
                out[ks] = vs
        return out
    return {}

def call_is_field(call):
    # fields.Char(...), fields.Many2one(...), etc.
    return isinstance(call.func, ast.Attribute) and getattr(call.func.value, 'id', None) == 'fields'

def field_type(call):
    if isinstance(call.func, ast.Attribute):
        return call.func.attr.lower()
    return 'unknown'

def kwarg_val(kwargs, name):
    for kw in kwargs:
        if kw.arg == name:
            if isinstance(kw.value, ast.Constant):
                return kw.value.value
            if isinstance(kw.value, (ast.List, ast.Tuple)):
                vals = []
                for elt in kw.value.elts:
                    if isinstance(elt, ast.Constant):
                        vals.append(elt.value)
                return vals
    return None

def first_arg_str(call):
    if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
        return call.args[0].value
    return None

def decorator_name(dec):
    # Handle api.depends('x'), api.constrains, api.onchange
    if isinstance(dec, ast.Attribute) and isinstance(dec.value, ast.Name):
        if dec.value.id == 'api':
            return f"api.{dec.attr}"
    if isinstance(dec, ast.Call):
        return decorator_name(dec.func)
    return None

index = {
    'models': {}
}

for root in roots:
    if not os.path.exists(root):
        continue
    for dirpath, _dirnames, filenames in os.walk(root):
        if '/tests/' in dirpath:
            continue
        for fn in filenames:
            if not fn.endswith('.py'):
                continue
            path = os.path.join(dirpath, fn)
            # only scan typical model files to contain noise
            if '/models/' not in path:
                continue
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    src = f.read()
                tree = ast.parse(src)
            except Exception:
                continue

            module_name = None
            # module name is the folder under root
            try:
                parts = path.split('/')
                if 'addons' in parts:
                    i = parts.index('addons')
                    if i + 1 < len(parts):
                        module_name = parts[i + 1]
                elif 'enterprise' in parts:
                    i = parts.index('enterprise')
                    if i + 1 < len(parts):
                        module_name = parts[i + 1]
            except Exception:
                pass

            for node in tree.body:
                if not isinstance(node, ast.ClassDef):
                    continue
                if not any(is_model_base(b) for b in node.bases):
                    continue
                cls = node
                m = {
                    'class': cls.name,
                    'module': module_name or 'unknown',
                    'file': path,
                    'description': None,
                    'inherits': [],
                    'delegates': {},
                    'fields': {},
                    'methods': [],
                    'decorators': {},
                }
                model_name = None

                for elem in cls.body:
                    if isinstance(elem, ast.Assign):
                        # _name, _description, _inherit, _inherits
                        for tgt in elem.targets:
                            if isinstance(tgt, ast.Name):
                                if tgt.id == '_name':
                                    model_name = str_const(elem.value) or model_name
                                elif tgt.id == '_description':
                                    m['description'] = str_const(elem.value)
                                elif tgt.id == '_inherit':
                                    m['inherits'] = list_of_str(elem.value)
                                elif tgt.id == '_inherits':
                                    m['delegates'] = dict_of_str(elem.value)
                                else:
                                    # field assignment? field = fields.X(...)
                                    if isinstance(elem.value, ast.Call) and call_is_field(elem.value):
                                        ftype = field_type(elem.value)
                                        required = bool(kwarg_val(elem.value.keywords, 'required'))
                                        store = bool(kwarg_val(elem.value.keywords, 'store'))
                                        string = kwarg_val(elem.value.keywords, 'string')
                                        compute = kwarg_val(elem.value.keywords, 'compute')
                                        related = kwarg_val(elem.value.keywords, 'related')
                                        rel = None
                                        inverse = None
                                        selection = None
                                        if ftype == 'many2one':
                                            rel = kwarg_val(elem.value.keywords, 'comodel_name') or first_arg_str(elem.value)
                                        elif ftype in ('one2many', 'many2many'):
                                            rel = kwarg_val(elem.value.keywords, 'comodel_name') or kwarg_val(elem.value.keywords, 'relation')
                                            inverse = kwarg_val(elem.value.keywords, 'inverse_name')
                                        elif ftype == 'selection':
                                            sel = kwarg_val(elem.value.keywords, 'selection')
                                            if not sel:
                                                # try first arg
                                                sel = first_arg_str(elem.value)
                                            selection = sel
                                        m['fields'][tgt.id] = {
                                            'type': ftype,
                                            'string': string,
                                            'required': required,
                                            'store': store,
                                            'relation': rel,
                                            'inverse_name': inverse,
                                            'selection': selection,
                                            'compute': compute,
                                            'related': related,
                                        }
                    elif isinstance(elem, ast.FunctionDef):
                        m['methods'].append(elem.name)
                        decs = []
                        for d in elem.decorator_list:
                            dn = decorator_name(d)
                            if dn in ('api.depends', 'api.constrains', 'api.onchange', 'api.model_create_multi'):
                                args = []
                                if isinstance(d, ast.Call):
                                    for a in d.args:
                                        if isinstance(a, ast.Constant) and isinstance(a.value, str):
                                            args.append(a.value)
                                decs.append({'type': dn.split('.')[-1], 'args': args})
                        if decs:
                            m['decorators'][elem.name] = decs

                if model_name:
                    index['models'][model_name] = m

print(json.dumps(index))
"""

    py = header + body

    docker = DockerClientManager()
    exec_result = docker.exec_run(container, ["python3", "-c", py], timeout=120)
    if not exec_result.get("success"):
        return {
            "success": False,
            "error": exec_result.get("stderr") or exec_result.get("output", "AST index failed"),
            "error_type": exec_result.get("error", "AstIndexError"),
            "container": container,
        }
    try:
        raw = exec_result.get("stdout", "{}")
        data = __import__("json").loads(raw)
        return data
    except Exception as e:
        return {"success": False, "error": f"Failed to parse AST index: {e!s}", "error_type": type(e).__name__}
