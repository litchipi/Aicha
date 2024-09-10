import sys
import json
import time
import os
from gpt4all import GPT4All

SUPPORTED_MODELS = {
    "hermes": "Nous-Hermes-2-Mistral-7B-DPO.Q4_0.gguf",
    "llama": "Meta-Llama-3-8B-Instruct.Q4_0.gguf",
}

def disp_color(r, g, b, *msg, **kwargs):
    print(color(r, g, b), end="")
    print(*msg, **kwargs)
    print("\033[0m", end="")

def color(r, g, b):
    return f"\033[38;2;{r};{g};{b}m"

def reset():
    return "\033[0m"

class Chat(GPT4All):
    FILENAME_GENERATION_PROMPT = "Create a short filename for this conversation, using key words representing what the user was asking. Output the filename in valid JSON using the key \"conversation_filename\", only output JSON data."

    SYSTEM_PROMPT = """
    You are a useful AI made to empower the user with knowledge from the Internet. Your answers are clear, concise, precise, does not contain any superfluous text.
    The answers are using lists and paragraphs to organise the content in a readable way.
    """
    def __init__(self, model, model_dir=".model", chat_dir=".chat"):
        if model not in SUPPORTED_MODELS:
            print("Model not supported")
            print("Supported models are:")
            for mod in SUPPORTED_MODELS:
                print(f"- {mod}")
            sys.exit(1)

        self.msg_system("Loading model", model.capitalize())
        os.makedirs(model_dir, exist_ok=True)
        self.model_dir = model_dir

        GPT4All.__init__(self,
            model_name = SUPPORTED_MODELS[model],
            model_path = self.model_dir,
            allow_download = True,
            n_threads = 16,
            n_ctx = 1 << 15,
        )

        os.makedirs(chat_dir, exist_ok=True)
        self.chat_dir = chat_dir
        self._history = [{"role": "system", "content": self.SYSTEM_PROMPT}]
        self._current_prompt_template = self.config["promptTemplate"]

    def msg_system(self, *msg):
        disp_color(128, 128, 128, *msg)

    def msg_ai(self, *msg):
        disp_color(255, 128, 200, *msg)

    def token_callback(self, id, token):
        try:
            self.response_buffer.append(token)

            if self.disp_tokens:
                sys.stdout.write(token)
                sys.stdout.flush()
        except KeyboardInterrupt:
            self.msg_system("Interrupted")
            return False
        except:
            self.msg_system("Interrupted")
            return False

        return self.continue_token_generation
    
    def ask(self, question, **kwargs):
        config = dict(
            max_tokens=409600,
            temp = 0.85,
            top_k = 40,
            top_p = 0.4,
            repeat_penalty = 1.18,
            repeat_last_n = 64,
        )
        config.update(kwargs)
        config["streaming"] = False

        self.response_buffer = []
        self.disp_tokens=True
        self.continue_token_generation = True
        try:
            print(color(255, 128, 200), end="")
            response = self.generate(question, callback=self.token_callback, **config)
        except KeyboardInterrupt:
            self.msg_system("Interrupt\n")
        finally:
            print(reset(), end="")
            self.continue_token_generation = False
        print("")
        response = ''.join(self.response_buffer)
        return response

    def run(self):
        while True:
            try:
                question = input(color(128, 255, 200) + "> ").strip()
                print(reset(), end="")
            except KeyboardInterrupt:
                self.msg_system("Stopping\n")
                break

            if len(question) == 0:
                continue

            # TODO    Have a handler for different kind of commands
            if question == "/quit":
                self.msg_system("Stopping\n")
                break

            self.ask(question)

        if len(self._history) == 1:    # No more than the first system prompt
            return

        self.msg_system("Generating a filename for this conversation")
        filename = self.generate_filename()
        self.msg_system(f"Saving under filename {filename}")
        with open(os.path.join(self.chat_dir, filename), "w") as f:
            for line in self.current_chat_session:
                if line["role"] == "user":
                    if line["content"] == self.FILENAME_GENERATION_PROMPT:
                        break
                    f.write("USER> " + line["content"] + "\n\n")
                elif line["role"] == "assistant":
                    f.write("AI> " + line["content"] + "\n\n")

    def generate_filename(self):
        self.disp_tokens = False
        filename = "chat_" + str(int(time.time()))
        ntry = 0
        while ntry < 5:
            try:
                data = self.generate(
                    self.FILENAME_GENERATION_PROMPT,
                    max_tokens=64,
                    temp = 0.60,
                )
            except KeyboardInterrupt:
                break

            try:
                data = json.loads(data)
                filename = data["conversation_filename"]
            except KeyboardInterrupt:
                break
            except Exception as err:
                self.msg_system(f"Invalid JSON generated: {err}")

            ntry += 1
        return filename

# TODO    Add a command for RAG:
#    - Analysis of a folder containing data files (depending on supported filenames)
#        Iterate through list of files, shasum of filenames & contents
#        Analyse all the files, save the result with shasum (so skip is result already there)
#    - Use analysis of a folder as a DB for RAG
#    - Insert content of database in prompt to generate answer

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: aicha <model> <model_dir> <chat_dir>")
        sys.exit(1)

    bot = Chat(sys.argv[1],
        model_dir=os.path.abspath(sys.argv[2]),
        chat_dir=os.path.abspath(sys.argv[3]),
    )
    bot.run()
