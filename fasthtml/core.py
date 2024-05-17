# AUTOGENERATED! DO NOT EDIT! File to edit: ../00_core.ipynb.

# %% auto 0
__all__ = ['empty', 'date', 'snake2hyphens', 'RouteX', 'FastHTML']

# %% ../00_core.ipynb 2
import json, dateutil

from fastcore.utils import *
from fastcore.xml import *

from types import UnionType
from typing import Optional, get_type_hints, get_args, get_origin, Union, Mapping
from datetime import datetime
from dataclasses import dataclass,fields,is_dataclass,MISSING,asdict
from inspect import isfunction,ismethod,signature,Parameter
from functools import wraps, partialmethod

from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import Response, HTMLResponse, FileResponse, JSONResponse
from starlette.requests import Request
from starlette.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette._utils import is_async_callable

# %% ../00_core.ipynb 5
empty = Parameter.empty

# %% ../00_core.ipynb 6
def _wrap_resp(resp, cls):
    if isinstance(resp, Response): return resp
    if cls is not empty: return cls(resp)
    if isinstance(resp, (list,tuple)): return HTMLResponse(to_xml(resp))
    if isinstance(resp, str): cls = HTMLResponse 
    elif isinstance(resp, Mapping): cls = JSONResponse 
    else:
        resp = str(resp)
        cls = HTMLResponse
    return cls(resp)

# %% ../00_core.ipynb 7
def _fix_anno(t):
    origin = get_origin(t)
    if origin is Union or origin is UnionType:
        t = first(o for o in get_args(t) if o!=type(None))
    if t==bool: return str2bool
    return t

# %% ../00_core.ipynb 8
def date(s): return dateutil.parser.parse(s)

# %% ../00_core.ipynb 9
def _form_arg(fld, body):
    res = body.get(fld.name, None)
    if not res: res = fld.default
    assert res is not MISSING
    anno = _fix_anno(fld.type)
    if res is not None: res = anno(res)
    return res

# %% ../00_core.ipynb 10
async def _from_body(req, arg, p):
    body = await req.form()
    cargs = {o.name:_form_arg(o, body) for o in fields(p.annotation)}
    return p.annotation(**cargs)

# %% ../00_core.ipynb 11
def snake2hyphens(s):
    s = snake2camel(s)
    return camel2words(s, '-')

# %% ../00_core.ipynb 12
async def _find_p(req, arg:str, p):
    if is_dataclass(p.annotation): return await _from_body(req, arg, p)
    res = req.path_params.get(arg, None)
    if not res: res = req.query_params.get(arg, None)
    if not res: res = req.cookies.get(arg, None)
    if not res: res = req.headers.get(snake2hyphens(arg), None)
    if not res: res = p.default
    if res is empty: return None
    anno = _fix_anno(p.annotation)
    if res is not None and anno is not empty: res = anno(res)
    return res

# %% ../00_core.ipynb 13
async def _wrap_req(req, params):
    items = [(k,v) for k,v in params.items()
             if v.annotation is not empty or v.default is not empty]
    if len(params)==1 and not items: return [req]
    return [await _find_p(req, arg, p) for arg,p in items]

# %% ../00_core.ipynb 14
def _wrap_ep(f):
    if not (isfunction(f) or ismethod(f)): return f
    sig = signature(f)
    params = sig.parameters
    cls = sig.return_annotation

    async def _f(req):
        req = await _wrap_req(req, params)
        resp = f(*req)
        if is_async_callable(f): resp = await resp
        return _wrap_resp(resp, cls)
    return _f

# %% ../00_core.ipynb 15
class RouteX(Route):
    def __init__(self, path, endpoint, *args, **kw):
        ep = _wrap_ep(endpoint)
        super().__init__(path, ep, *args, **kw)

# %% ../00_core.ipynb 16
class FastHTML:
    def __init__(self): self.rd = {}

    async def __call__(self, scope, recv, send):
        routes = list(self.rd.values())
        app = Starlette(debug=True, routes=routes)
        return await app(scope, recv, send)

    def add_route(self, route):
        meth = first(route.methods)
        self.rd[(route.path,meth)] = route
        
    def route(self, path, meth='GET'):
        def _inner(f):
            self.add_route(RouteX(path, f, methods=[meth]))
            return f
        return _inner

for o in 'get post put delete patch head trace options'.split():
    setattr(FastHTML, o, partialmethod(FastHTML.route, meth=o.capitalize()))
