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
        "description": "HuBERT — self-supervised speech representation (12-layer base model). "
                       "Per Pasad, Chou, Livescu (ASRU 2021), HuBERT-base shows phonetic content "
                       "peaking around layers 7-9, with word-level info further up at layers 9-11. "
                       "Speaker information concentrates in EARLY layers (1-4); layer 12 is closer "
                       "to the masked-prediction target and is content-leaning, not speaker-leaning. "
                       "Earlier vpstack docs claimed 'layer 6 = content / layer 12 = speaker' — "
                       "that claim was partially wrong (corrected 2026-04-28 audit). For voice "
                       "anonymization, ContentVec (Qian et al., ICML 2022) is the disentanglement-tuned "
                       "variant typically used.",
        "tradeoffs": {
            "layer_6": "Pre-content peak; some phonetic + some residual speaker. Common in VP recipes.",
            "layer_7_to_9": "Phonetic content peak per Pasad et al. ASRU 2021. Default for most uses.",
            "layer_1_to_4": "Speaker-leaning. Avoid for content encoder in anonymization.",
            "layer_12": "Content-leaning (close to masked target). Not speaker-leaning despite earlier claims.",
        },
        "known_issues": [
            "Layer 6 causes measurable speaker leakage on utterances shorter than ~1 second — "
            "the phoneme context window is too narrow for good disentanglement. Switch to layer 9.",
            "facebook/hubert-base-ls960 (16kHz) produces artifacts when resampled input differs "
            "from 16kHz — always resample before encode, never rely on HF pipeline auto-resample.",
        ],
        "papers": [
            "Hsu et al., HuBERT, arXiv:2106.07447",
            "Pasad, Chou, Livescu, Layer-Wise Analysis of a Self-Supervised Speech Representation Model, ASRU 2021, arXiv:2107.04734",
            "Qian et al., ContentVec (disentanglement-tuned variant), ICML 2022",
        ],
        "license": "Apache 2.0 (facebook/hubert-base-ls960)",
    },
    "contentvec": {
        "description": "ContentVec — disentanglement-tuned HuBERT variant (Qian et al., ICML 2022). "
                       "Explicitly trained to suppress speaker information from the content representation. "
                       "Superior to vanilla HuBERT for voice anonymization because the disentanglement "
                       "is learned, not assumed from layer selection. Recommended over HuBERT-base "
                       "whenever the task is anonymization, not just content extraction.",
        "tradeoffs": {
            "layer_9": "Recommended — best content/speaker disentanglement per Qian et al.",
            "vs_hubert": "EER improvement of 2-5pp over vanilla HuBERT layer 7-9 on LibriSpeech dev.",
        },
        "known_issues": [
            "ContentVec-500 (500 units) not compatible with all HiFi-GAN vocoders trained on "
            "HuBERT-base embeddings — verify vocoder was trained on matching encoder.",
        ],
        "papers": [
            "Qian et al., ContentVec: An Improved Self-Supervised Speech Representation by Disentangling Speakers, ICML 2022",
        ],
        "license": "MIT (AIMiranker/contentvec)",
    },
    "wavlm": {
        "description": "WavLM — masked speech prediction + denoising pre-training (Chen et al., 2022). "
                       "Currently the best-performing self-supervised model on SUPERB benchmark. "
                       "WavLM-Large outperforms HuBERT-large on most speech tasks. Many VP2026 "
                       "systems will use WavLM-Large as content encoder instead of HuBERT-base.",
        "tradeoffs": {
            "wavlm_large_vs_hubert_base": "EER improvement 3-8pp in preliminary VP2026 experiments. "
                                           "Cost: 300M params vs 95M — ~3x inference time.",
            "layer_selection": "Layers 6-9 recommended for content; layers 1-4 still speaker-leaning.",
        },
        "known_issues": [
            "WavLM-Large is 300M params — too large for CPU inference on most laptops. "
            "Requires GPU with >= 8GB VRAM for real-time inference on 10s utterances.",
            "microsoft/wavlm-large uses float32 by default; fp16 quantization can cause "
            "NaN gradients on short utterances during finetuning.",
        ],
        "papers": [
            "Chen et al., WavLM: Large-Scale Self-Supervised Pre-Training for Full Stack Speech Processing, arXiv:2110.13900",
        ],
        "license": "MIT (microsoft/wavlm-large)",
    },
    "ecapa-tdnn": {
        "description": "ECAPA-TDNN — speaker embedding network. Standard backbone for "
                       "VP2026 speaker similarity / linkability eval. The 'farthest-point' "
                       "strategy uses ECAPA embeddings to pick a target voice maximally "
                       "distant from the source speaker.",
        "tradeoffs": {
            "vanilla": "Standard pretrained — fastest, most compatible",
            "farthest_point_selection": "Stronger anonymization vs random target voice; +5-10% time",
            "192ch_vs_512ch": "192ch (default pretrained) is 4x faster; 512ch adds ~1-2pp EER improvement.",
        },
        "known_issues": [
            "ECAPA 192ch + HiFi-GAN v1 universal produces phase artifacts above 4kHz — "
            "use LibriTTS-finetuned HiFi-GAN or check output spectrograms.",
            "speechbrain/spkrec-ecapa-voxceleb was trained on VoxCeleb1+2 (English celebrities). "
            "Farthest-point target selection degrades when the enrollment set is non-English — "
            "the embedding space geometry does not transfer well.",
        ],
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
        "known_issues": [
            "v1 universal weights trained at 22050 Hz; VP2026 data is 16kHz. "
            "Use a 16kHz-finetuned checkpoint or apply sample-rate mismatch will cause artifacts.",
            "HiFi-GAN inference is sensitive to mel-spectrogram normalization — verify that "
            "the mel stats (mean/std) used at inference match those used during vocoder training.",
        ],
        "papers": ["Kong, Kim, Bae, NeurIPS 2020"],
        "license": "MIT (jik876/hifi-gan)",
    },
    "mcadams": {
        "description": "McAdams coefficient transformation — classical signal-processing "
                       "anonymization. The B1 baseline. No neural model needed; modifies LPC "
                       "pole angles to shift formants. Fast, weak anonymization.",
        "tradeoffs": {
            "alpha_0.8": "Standard B1 setting (Patino); mild anonymization, low WER cost.",
            "alpha_0.75": "Slightly stronger; outperforms α=0.8 on female speakers in LibriSpeech dev.",
            "alpha_0.5": "Stronger but more artifacts; notable WER regression on fast speech.",
        },
        "known_issues": [
            "α=0.5 causes audible artifacts on utterances with F0 < 100 Hz (low-pitched male speakers). "
            "Clip α to [0.6, 0.9] range for production use.",
            "frame_length_ms default was 25ms in VP2020 but 20ms in VP2026 Eval Plan (corrected 2026-04-28). "
            "Verify your recipe uses frame_length_ms=20 or results will not match canonical B1 numbers.",
        ],
        "papers": ["Patino et al., VP2020 baseline B1"],
        "license": "N/A (signal processing, no model weights)",
    },
    "plda": {
        "description": "PLDA (Probabilistic Linear Discriminant Analysis) — scoring backend "
                       "for ASV attacker. Alternative to cosine scoring. Requires domain "
                       "adaptation when training data distribution differs from evaluation data.",
        "tradeoffs": {
            "vs_cosine": "PLDA often +1-3pp EER (more discriminative) but requires in-domain training data.",
            "diagonal_plda": "Faster, comparable accuracy to full PLDA for most VP use cases.",
        },
        "known_issues": [
            "PLDA adapted on original (non-anonymized) data will not transfer well to anonymized "
            "embeddings — always adapt on anonymized enrollment data for semi-informed condition.",
        ],
        "papers": ["Prince & Elder, ICCV 2007"],
        "license": "N/A (algorithm)",
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
