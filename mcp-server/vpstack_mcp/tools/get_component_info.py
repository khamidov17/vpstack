"""vp_get_component_info — look up tradeoff matrix for a known voice-privacy component.

Sources from a hand-curated YAML in the recipe package (component_info.yaml).
Updates ship with vpstack releases. v0.2 may add a `vpstack-config refresh-components`
command to pull a newer YAML between releases.
"""

from __future__ import annotations

from pathlib import Path

from vpstack_mcp.errors import ToolResult, ok, err


# In v0.1.0-dev we ship a small in-tree dict. As the catalog grows, move to YAML in
# speechbrain_voice_anon/component_info.yaml.
_BUILTIN_COMPONENTS: dict[str, dict] = {
    "hubert": {
        "description": "HuBERT — self-supervised speech representation. Layer choice matters: "
                       "layer 6 emphasizes content (better for anonymization disentanglement), "
                       "layer 12 emphasizes speaker identity.",
        "tradeoffs": {
            "layer_6": "Content-leaning; better speaker anonymization, slightly higher WER risk",
            "layer_12": "Speaker-leaning; not recommended for content encoder in anonymization",
        },
        "papers": [
            "Hsu et al., HuBERT: arXiv:2106.07447",
            "Liu et al. 2024 (layer-choice analysis for VP2024)",
        ],
        "license": "Apache 2.0 (facebook/hubert-base-ls960)",
    },
    "ecapa-tdnn": {
        "description": "ECAPA-TDNN — speaker embedding network. Standard backbone for "
                       "VP2026 speaker similarity / linkability eval. The 'farthest-point' "
                       "strategy uses ECAPA embeddings to pick a target voice maximally "
                       "distant from the source speaker.",
        "tradeoffs": {
            "vanilla": "Standard pretrained — fastest, most compatible",
            "farthest_point_selection": "Stronger anonymization vs random target voice; +5-10% time",
        },
        "papers": ["Desplanques et al., Interspeech 2020"],
        "license": "Apache 2.0 (speechbrain/spkrec-ecapa-voxceleb)",
    },
    "hifi-gan": {
        "description": "HiFi-GAN — high-fidelity neural vocoder. Used in VP2026 to synthesize "
                       "anonymized audio from content + target-speaker representations.",
        "tradeoffs": {
            "v1_universal": "jik876 reference universal weights; generic but fast",
            "vp_finetuned": "Fine-tuned on LibriTTS for anonymization-specific output; recommended",
        },
        "papers": ["Kong, Kim, Bae, NeurIPS 2020"],
        "license": "MIT (jik876/hifi-gan)",
    },
    "mcadams": {
        "description": "McAdams coefficient transformation — classical signal-processing "
                       "anonymization. The B1 baseline. No neural model needed; modifies LPC "
                       "pole angles to shift formants. Fast, weak anonymization.",
        "tradeoffs": {
            "alpha_0.8": "Standard B1 setting; mild anonymization, low quality cost",
            "alpha_0.5": "Stronger but more artifacts",
        },
        "papers": ["Patino et al., VP2020 baseline B1"],
        "license": "N/A (signal processing, no model weights)",
    },
}


def handle(component_name: str) -> ToolResult:
    """Return tradeoff info for a known component, or UNKNOWN_COMPONENT error."""
    key = component_name.lower().replace("_", "-")
    info = _BUILTIN_COMPONENTS.get(key)
    if info is None:
        # Helpful error: list known components
        known = sorted(_BUILTIN_COMPONENTS.keys())
        return err(
            "UNKNOWN_COMPONENT",
            f"no tradeoff info for component: {component_name}",
            f"Known components: {', '.join(known)}. "
            f"To add a component, edit speechbrain_voice_anon/component_info.yaml.",
        )
    return ok({
        "component": key,
        **info,
    })
