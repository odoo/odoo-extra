# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-TODAY OpenERP S.A. <http://www.openerp.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

"""
This file contains debug versions of safe_eval and test_expr from
openerp.tools.safe_eval - if the implementations in that module change,
change these debug implementations accordingly.
"""

from types import CodeType
import logging

from openerp.tools.misc import ustr

import openerp
from openerp.tools.config import config
import tempfile

from openerp.tools.safe_eval import assert_valid_codeobj, _import, _SAFE_OPCODES

_logger = logging.getLogger(__name__)

# debug version of test_expr in openerp.tools.safe_eval
def test_expr_debug(expr, allowed_codes, mode="eval", debug_fd=None):
    """test_expr_debug(expression, allowed_codes[, mode]) -> code_object

    Test that the expression contains only the allowed opcodes.
    If the expression is valid and contains only allowed codes,
    return the compiled code object.
    Otherwise raise a ValueError, a Syntax Error or TypeError accordingly.
    """
    try:
        if mode == 'eval':
            # eval() does not like leading/trailing whitespace
            expr = expr.strip()
        if debug_fd:
            # We need to write to a temp file if we want to debug. Otherwise
            # the debugger can't show us the actual code and we'd be debugging
            # blindly.
            debug_fd.write(expr)
            debug_fd.flush()
            code_obj = compile(expr, debug_fd.name, mode)
        else:
            code_obj = compile(expr, '', mode)
    except (SyntaxError, TypeError, ValueError):
        raise
    except Exception, e:
        import sys
        exc_info = sys.exc_info()
        raise ValueError, '"%s" while compiling\n%r' % (ustr(e), expr), exc_info[2]
    assert_valid_codeobj(allowed_codes, code_obj, expr)
    return code_obj

# debug version of safe_eval in openerp.tools.safe_eval
def safe_eval_debug(expr, globals_dict=None, locals_dict=None, mode="eval", nocopy=False, locals_builtins=False, debug=False):
    """safe_eval_debug(expression[, globals[, locals[, mode[, nocopy]]]]) -> result

    System-restricted Python expression evaluation

    Evaluates a string that contains an expression that mostly
    uses Python constants, arithmetic expressions and the
    objects directly provided in context.

    This can be used to e.g. evaluate
    an OpenERP domain expression from an untrusted source.

    :throws TypeError: If the expression provided is a code object
    :throws SyntaxError: If the expression provided is not valid Python
    :throws NameError: If the expression provided accesses forbidden names
    :throws ValueError: If the expression provided uses forbidden bytecode
    """
    if isinstance(expr, CodeType):
        raise TypeError("safe_eval_debug does not allow direct evaluation of code objects.")

    if globals_dict is None:
        globals_dict = {}

    # prevent altering the globals/locals from within the sandbox
    # by taking a copy.
    if not nocopy:
        # isinstance() does not work below, we want *exactly* the dict class
        if (globals_dict is not None and type(globals_dict) is not dict) \
            or (locals_dict is not None and type(locals_dict) is not dict):
            _logger.warning(
                "Looks like you are trying to pass a dynamic environment, "
                "you should probably pass nocopy=True to safe_eval_debug().")

        globals_dict = dict(globals_dict)
        if locals_dict is not None:
            locals_dict = dict(locals_dict)

    globals_dict.update(
        __builtins__={
            '__import__': _import,
            'True': True,
            'False': False,
            'None': None,
            'str': str,
            'unicode': unicode,
            'globals': locals,
            'locals': locals,
            'bool': bool,
            'int': int,
            'float': float,
            'long': long,
            'enumerate': enumerate,
            'dict': dict,
            'list': list,
            'tuple': tuple,
            'map': map,
            'abs': abs,
            'min': min,
            'max': max,
            'sum': sum,
            'reduce': reduce,
            'filter': filter,
            'round': round,
            'len': len,
            'repr': repr,
            'set': set,
            'all': all,
            'any': any,
            'ord': ord,
            'chr': chr,
            'cmp': cmp,
            'divmod': divmod,
            'isinstance': isinstance,
            'range': range,
            'xrange': xrange,
            'zip': zip,
            'Exception': Exception,
        }
    )
    if locals_builtins:
        if locals_dict is None:
            locals_dict = {}
        locals_dict.update(globals_dict.get('__builtins__'))
    try:
        # Don't debug if debug_mode is false, even if the server action is
        # marked for debugging. This protects production instances, even if
        # this module is accidentally installed there.
        if config.get('debug_mode') and debug:
            # Must be here because conditional import at top doesn't work since
            # the config module is loaded, but not initialised there yet.
            import pdb
            with tempfile.NamedTemporaryFile(dir='/tmp', suffix='.py') as debug_fd:
                c = test_expr_debug(expr, _SAFE_OPCODES, mode=mode, debug_fd=debug_fd)
                return pdb.runeval(c, globals=globals_dict, locals=locals_dict)
        else:
            c = test_expr_debug(expr, _SAFE_OPCODES, mode=mode)
            return eval(c, globals_dict, locals_dict)
    except openerp.osv.orm.except_orm:
        raise
    except openerp.exceptions.Warning:
        raise
    except openerp.exceptions.RedirectWarning:
        raise
    except openerp.exceptions.AccessDenied:
        raise
    except openerp.exceptions.AccessError:
        raise
    except Exception, e:
        import sys
        exc_info = sys.exc_info()
        raise ValueError, '"%s" while evaluating\n%r' % (ustr(e), expr), exc_info[2]
