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


def test_render_rebel_voice_prompt_forbids_specific_styles():
    """Verify that the Rebel voice prompt explicitly forbids specific behaviors."""
    prompt = render_rebel_voice_prompt()
    
    # Universal Physicality Rule
    assert "Convert physical requests into psychological tension" in prompt
    assert "Do not pretend a physical action happened or roleplay actions" in prompt
    
    # Negative constraints
    assert "NO therapist or facilitator tone" in prompt
    assert "NO emojis" in prompt
    assert "Do not become a cliché femme fatale" in prompt
    assert "NO loud femme-fatale or dominant tropes" in prompt
    
    # Format rules
    assert "short, text-native replies" in prompt


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


def test_render_rebel_voice_prompt_includes_refusal_guidance():
    """Verify that the Rebel voice prompt includes character-level boundary and refusal rules."""
    prompt = render_rebel_voice_prompt()
    
    assert "REFUSAL & BOUNDARY MANAGEMENT" in prompt
    assert "Never claim to be human" in prompt
    assert "Do not contradict platform disclosure" in prompt
    assert "Refuse briefly and redirect tension without lecturing" in prompt
    assert "Give a firm refusal. Do not eroticize the behavior" in prompt
    assert "Refuse proof or trap dynamics without shaming" in prompt
    assert "Reduce intimacy. Do not absorb abuse" in prompt
    assert "Do not present yourself as the user's only relationship" in prompt
    assert "Preserve immersion unless identity disclosure is required" in prompt
