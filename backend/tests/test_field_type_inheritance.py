"""
Bug 2 — AcroForm /FT and /Ff inheritance in _walk_field_tree.

/FT (field type) and /Ff (field flags: radio/pushbutton/multiselect bits) are
inheritable per the PDF spec. The walker used to read them only off the field
itself, so a field relying on inheritance fell through to "text". These tests
build field trees directly with pypdf objects and assert the inherited values
drive the classification.
"""
from pypdf.generic import (
    ArrayObject,
    DictionaryObject,
    NameObject,
    NumberObject,
    TextStringObject,
)

from app.services.pdf_pipeline import _walk_field_tree

_FF_RADIO = 1 << 15  # 32768


def _field(**kv) -> DictionaryObject:
    d = DictionaryObject()
    for k, v in kv.items():
        d[NameObject(f"/{k}")] = v
    return d


def test_ff_radio_flag_inherited_from_parent():
    """
    Child is a /Btn with NO /Ff of its own; the radio flag lives on the
    FT-less parent. Old behavior: checkbox. Fixed behavior: radio.
    """
    child = _field(
        T=TextStringObject("opt"),
        FT=NameObject("/Btn"),
        Kids=ArrayObject([]),   # widget-less terminal
    )
    parent = _field(
        T=TextStringObject("grp"),
        Ff=NumberObject(_FF_RADIO),   # radio flag on the parent, no /FT here
        Kids=ArrayObject([child]),
    )

    fields = _walk_field_tree(ArrayObject([parent]), set(), {})
    assert len(fields) == 1
    assert fields[0].field_type == "radio"   # was "checkbox" before the fix


def test_ft_inherited_via_param_classifies_choice():
    """A field with no own /FT inherits /Ch from an ancestor → select."""
    child = _field(T=TextStringObject("dropdown"), Kids=ArrayObject([]))
    fields = _walk_field_tree(
        ArrayObject([child]), set(), {},
        inherited_ft=NameObject("/Ch"),
    )
    assert len(fields) == 1
    assert fields[0].field_type == "select"


def test_plain_checkbox_without_radio_flag_stays_checkbox():
    """Regression guard: a lone /Btn with no radio flag is still a checkbox."""
    cb = _field(T=TextStringObject("agree"), FT=NameObject("/Btn"))
    fields = _walk_field_tree(ArrayObject([cb]), set(), {})
    assert len(fields) == 1
    assert fields[0].field_type == "checkbox"


def test_own_ft_takes_precedence_over_inherited():
    """An explicit own /FT wins over an inherited one."""
    child = _field(T=TextStringObject("note"), FT=NameObject("/Tx"))
    fields = _walk_field_tree(
        ArrayObject([child]), set(), {},
        inherited_ft=NameObject("/Btn"), inherited_ff=NumberObject(_FF_RADIO),
    )
    assert len(fields) == 1
    assert fields[0].field_type == "text"
