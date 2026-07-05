"""Regression test for Gemini-via-OpenRouter tool-name namespace prefix bug."""
import importlib

from pika.compat.gemini import install


def _fresh_get_function_call():
    import agno.utils.functions as functions_mod
    import agno.utils.tools as tools_mod
    import pika.compat.gemini as compat

    importlib.reload(functions_mod)
    importlib.reload(tools_mod)
    compat._installed = False
    return functions_mod, tools_mod, compat


def _registered_functions():
    from agno.tools.function import Function

    return {"lookup_records": Function(name="lookup_records")}


def test_strips_namespace_prefix_when_unprefixed_name_registered():
    functions_mod, _tools_mod, compat = _fresh_get_function_call()
    compat.install()

    registered = _registered_functions()
    call = functions_mod.get_function_call("default_api.lookup_records", functions=registered)
    assert call is not None
    assert call.function is registered["lookup_records"]


def test_leaves_exact_match_untouched():
    functions_mod, _tools_mod, compat = _fresh_get_function_call()
    compat.install()

    registered = _registered_functions()
    call = functions_mod.get_function_call("lookup_records", functions=registered)
    assert call is not None
    assert call.function is registered["lookup_records"]


def test_does_not_fabricate_a_match_for_unknown_tool():
    functions_mod, _tools_mod, compat = _fresh_get_function_call()
    compat.install()

    registered = _registered_functions()
    call = functions_mod.get_function_call("default_api.delete_everything", functions=registered)
    assert call is None


def test_install_is_idempotent():
    functions_mod, _tools_mod, compat = _fresh_get_function_call()
    compat.install()
    once = functions_mod.get_function_call
    compat.install()
    assert functions_mod.get_function_call is once
