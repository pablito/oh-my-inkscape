# SPDX-License-Identifier: GPL-3.0-or-later
from omi_lib.mdlists.markdown import NBSP, ListBlock, Para, parse_markdown, refine_text
from omi_lib.mdlists.style import merge_style


def text_of(para):
    return "".join(r.text for r in para.runs)


def test_nested_lists_and_lazy_continuation():
    blocks = parse_markdown("- one\n  - child\n    continued\n- two\nlazy line\n")
    (lst,) = blocks
    assert [it.marker for it in lst.items] == ["-", "-"]
    first = lst.items[0]
    assert isinstance(first.blocks[1], ListBlock)
    assert text_of(first.blocks[1].items[0].blocks[0]) == "child continued"
    assert text_of(lst.items[1].blocks[0]) == "two lazy line"


def test_bullet_and_ordered_lists_are_split():
    blocks = parse_markdown("- a\n- b\n\n1. x\n2) y\na) z\n")
    assert len(blocks) == 2
    assert [it.ordered for it in blocks[1].items] == [True, True, True]
    assert [it.marker for it in blocks[1].items] == ["1.", "2)", "a)"]


def test_inline_styles_and_literal_asterisks():
    (para,) = parse_markdown("**Fail once:** results A* or D* and ***both*** \\*x")
    runs = [(r.text, r.bold, r.italic) for r in para.runs]
    assert runs[0] == ("Fail once:", True, False)
    assert ("both", True, True) in runs
    assert "A* or D*" in text_of(para) and text_of(para).endswith("*x")


def test_headings_and_hard_breaks():
    blocks = parse_markdown("## Title\n\nline one  \nline two\n")
    assert blocks[0].heading == 2
    assert text_of(blocks[1]) == "line one\nline two"


def test_smart_punctuation_and_nobreak():
    style = merge_style()
    blocks = parse_markdown('Dice "ciao" e l\'altro... -- fine: −1 ZOC per [9.131, 9.141].')
    refine_text(blocks, style)
    t = text_of(blocks[0])
    assert "“ciao”" in t and "l’altro…" in t and " – fine" in t
    assert f"−1{NBSP}ZOC" in t and f"[9.131,{NBSP}9.141]" in t


def test_nobreak_does_not_glue_sentence_end():
    style = merge_style()
    blocks = parse_markdown("Ogni venerdì dalle 21:00. Portate i giochi.")
    refine_text(blocks, style)
    assert NBSP not in text_of(blocks[0])


def test_paragraph_type():
    assert isinstance(parse_markdown("plain text")[0], Para)
