import sys
import time
import os
from gpt4all import GPT4All

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".model")
CHAT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".chat")
os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(CHAT_DIR, exist_ok=True)

FILENAME_GENERATION_PROMPT = """
Create a very short filename for this conversation, using key words, output in JSON using the key \"conversation_filename\", only output JSON data.
"""

SYSTEM_PROMPT = """
"""

model = GPT4All(
    model_name = "Meta-Llama-3-8B-Instruct.Q4_0.gguf",
    model_path = MODEL_DIR,
    allow_download = True,
    n_threads = 16,
)


with model.chat_session():
    while True:
        try:
            question = input("> ")
        except:
            print("Stopping")
            print("")
            break

        if question == "/quit":
            print("Stopping")
            print("")
            break

        try:
            for token in model.generate(
                question,
                max_tokens=4096,
                streaming=True,
                temp = 0.7,
                top_k = 40,
                top_p = 0.4,
                repeat_penalty = 1.18,
                repeat_last_n = 64,
            ):
                sys.stdout.write(token)
                sys.stdout.flush()
        except KeyboardInterrupt:
            print("")
            print("Interrupted")
            continue
        finally:
            print("")

    filename = "chat_" + str(int(time.time()))
    ntry = 0
    while ntry < 5:
        data = model.generate(FILENAME_GENERATION_PROMPT, max_tokens=64)
        try:
            print(data)
            data = json.loads(data)
            filename = data["conversation_filename"]
            break
        except:
            print("Invalid JSON generated")
        ntry += 1

    print(f"Saving under filename {filename}")
    with open(os.path.join(CHAT_DIR, filename), "w") as f:
        for line in model.current_chat_session:
            if line["role"] == "user":
                f.write("USER> " + line["content"] + "\n\n")
            elif line["role"] == "assistant":
                f.write("AI> " + line["content"] + "\n\n")

sys.exit(0)
