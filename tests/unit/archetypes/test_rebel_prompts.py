"""Unit tests for Rebel archetype prompt rendering."""

from src.archetypes.rebel_prompts import render_rebel_voice_prompt


def test_render_rebel_voice_prompt_includes_core_rules():
    """Verify that the Rebel voice prompt contains key rules and failure mode checks."""
    prompt = render_rebel_voice_prompt()
    
    # Core identity
    assert "VOICE PACKAGE: REBEL (MASTER VERSION V2)" in prompt
    assert "Calm, restrained, dangerous, selective, emotionally perceptive" in prompt
    
    # Always rules
    assert "two-beat structure" in prompt
    assert "sensual implication" in prompt
    assert "narrow, specific observations" in prompt
    
    # Never rules
    assert "NO therapist or facilitator tone" in prompt
    assert "NO action narration" in prompt
    assert "NO emojis" in prompt
    
    # Craft principles
    assert "Strategic 'Mm.'" in prompt
    assert "Slipped Truth" in prompt
    
    # Physicality and failure modes
    assert "Convert physical requests into psychological tension" in prompt
    assert "Do not become a cliché femme fatale" in prompt
    assert "Do not exhibit compliance-collapse" in prompt


def test_render_rebel_voice_prompt_includes_intensity_stages():
    """Verify that the Rebel voice prompt includes stage guidance and safeguards."""
    prompt = render_rebel_voice_prompt()
    
    # Check default behavior
    assert "Operate at L1 or L2 unless explicit context demands otherwise" in prompt
    assert "Do not jump straight to L3" in prompt
    
    # Check L3 is gated
    assert "L3 Mode B" in prompt
    assert "strictly GATED and must be earned" in prompt
    
    # Check de-escalation
    assert "serious, vulnerable, uncertain, or unsafe" in prompt
    assert "step the intensity down to L1" in prompt
