FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

WORKDIR /workspace
ENV DEBIAN_FRONTEND=noninteractive \
    HF_HUB_ENABLE_HF_TRANSFER=1 \
    COMFY_PORT=8188

RUN apt-get update && apt-get install -y --no-install-recommends git wget curl && rm -rf /var/lib/apt/lists/*

# Python deps
RUN pip install --no-cache-dir runpod requests huggingface_hub hf_transfer

# ComfyUI + ноды Qwen-Image
RUN git clone https://github.com/comfyanonymous/ComfyUI.git && \
    mkdir -p /workspace/ComfyUI/custom_nodes
RUN git -C /workspace/ComfyUI/custom_nodes clone https://github.com/AIFSH/QwenImage-ComfyUI.git || true

# Лора и воркфлоу
RUN huggingface-cli download Danrisi/adorablegirls_qwen adorablegirls.safetensors --local-dir /workspace/ComfyUI/models/loras && \
    huggingface-cli download Danrisi/adorablegirls_qwen Qwen_danrisi.json --local-dir /workspace/workflows

COPY rp_handler.py /workspace/
CMD ["python", "-u", "/workspace/rp_handler.py"]
