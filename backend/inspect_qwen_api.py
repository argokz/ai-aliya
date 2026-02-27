import torch
from qwen_tts import Qwen3TTSModel

def inspect_model():
    print("Loading model for inspection...")
    try:
        model = Qwen3TTSModel.from_pretrained(
            "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
            device_map="cpu", # Use CPU for quick inspection
            torch_dtype=torch.float32
        )
        print("\nModel Attributes and Methods:")
        for attr in dir(model):
            if not attr.startswith("_"):
                print(f"- {attr}")
                
        # Also check for common synthesis method names
        suggestions = ["generate", "synthesis", "tts", "infer", "forward", "predict", "run"]
        print("\nCommon method checks:")
        for s in suggestions:
            if hasattr(model, s):
                print(f"[FOUND] {s}")
                
    except Exception as e:
        print(f"Inspection failed: {e}")

if __name__ == "__main__":
    inspect_model()
