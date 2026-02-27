import inspect
from qwen_tts import Qwen3TTSModel

def inspect_signature():
    # We dont even need to load weights for inspect.signature if we just need the class method
    sig = inspect.signature(Qwen3TTSModel.generate_voice_clone)
    print(f"generate_voice_clone signature: {sig}")
    
    # Also check other methods just in case
    print(f"generate_custom_voice signature: {inspect.signature(Qwen3TTSModel.generate_custom_voice)}")

if __name__ == "__main__":
    inspect_signature()
