import sys
import time
import os
from gpt4all import GPT4All

DEFAULT_MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".model")
DEFAULT_CHAT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".chat")

class Chat(GPT4All):
    FILENAME_GENERATION_PROMPT = "Create a very short filename for this conversation, output in JSON using the key \"conversation_filename\", only output JSON data."

    SYSTEM_PROMPT = """
    """
    def __init__(self, model_dir=DEFAULT_MODEL_DIR, chat_dir=DEFAULT_CHAT_DIR):
        os.makedirs(model_dir, exist_ok=True)
        self.model_dir = model_dir

        GPT4All.__init__(self,
            model_name = "Meta-Llama-3-8B-Instruct.Q4_0.gguf",
            model_path = self.model_dir,
            allow_download = True,
            n_threads = 16,
        )

        os.makedirs(chat_dir, exist_ok=True)
        self.chat_dir = chat_dir

    # TODO    Break this down into a much more modular code using methods & stuff
    def start_session(self):
        with self.chat_session():
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

                tokens = self.generate(
                        question,
                        max_tokens=4096,
                        streaming=True,
                        temp = 0.7,
                        top_k = 40,
                        top_p = 0.4,
                        repeat_penalty = 1.18,
                        repeat_last_n = 64,
                    )
                while True:
                    try:
                        token = next(tokens)
                    except StopIteration:
                        break
                    # FIXME     Segmentation fault if try to use prompt afterward
                    except KeyboardInterrupt:
                        del tokens
                        print("Interrupted")
                        break
                    sys.stdout.write(token)
                    sys.stdout.flush()

            filename = "chat_" + str(int(time.time()))
            ntry = 0
            while ntry < 5:
                data = self.generate(FILENAME_GENERATION_PROMPT, max_tokens=64)
                try:
                    print("text", data)
                    data = json.loads(data)
                    print("json", data)
                    filename = data["conversation_filename"]
                    print("filename", filename)
                    break
                except Exception as err:
                    print(f"Invalid JSON generated: {err}")
                ntry += 1

            print(f"Saving under filename {filename}")
            with open(os.path.join(CHAT_DIR, filename), "w") as f:
                for line in self.current_chat_session:
                    if line["role"] == "user":
                        if line["content"] == FILENAME_GENERATION_PROMPT:
                            break
                        f.write("USER> " + line["content"] + "\n\n")
                    elif line["role"] == "assistant":
                        f.write("AI> " + line["content"] + "\n\n")

        sys.exit(0)

# TODO    Use this code to stream elements and stop iteration when we want

from gpt4all import GPT4All
import sys

model = GPT4All('ggml-mpt-7b-chat')
message = sys.sysv[1]
messages = []
print( "Prompt: " + message )
messages.append({"role": "user", "content": message});
full_prompt = model._build_prompt(messages, True, True)
response_tokens = [];
def local_callback(token_id, response):
    decoded_token = response.decode('utf-8')
    response_tokens.append( decoded_token );

    # Do whatever you want with decoded_token here.

    return True

model.model._response_callback = local_callback
model.model.generate(full_prompt, streaming=False)
response = ''.join(response_tokens)
print ( "Response: " + response );
messages.append({"role": "assistant", "content": response});

# At this point, you can get another prompt from the user, re-run "_build_prompt()", and continue the conversation.
