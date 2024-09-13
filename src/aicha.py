#!/usr/bin/env python3
#-*-encoding:utf-8*-

import os
import sys
import json
import time
from gpt4all import GPT4All

from interface import set_ai_color, set_user_color, reset_style, msg_system, set_verbosity
from rag import KnowledgeLibrary

SUPPORTED_MODELS = {
    "hermes": "Nous-Hermes-2-Mistral-7B-DPO.Q4_0.gguf",
    "llama": "Meta-Llama-3-8B-Instruct.Q4_0.gguf",
}

class Aicha(GPT4All):
    FILENAME_GENERATION_PROMPT = "Create a short filename for this conversation, using key words representing what the user was asking. Output the filename in valid JSON using the key \"conversation_filename\", only output JSON data."

    SYSTEM_PROMPT = """
    You are a useful AI made to empower the user with knowledge from the Internet. Your answers are clear, concise, precise, does not contain any superfluous text.
    The answers are using lists and paragraphs to organise the content in a readable way.
    """
    def __init__(self,
             model,
             model_dir,
             chat_dir,
             rag,
             rag_nb_qry=10,
             rag_threshold=0.87,
         ):
        if model not in SUPPORTED_MODELS:
            print("Model not supported")
            print("Supported models are:")
            for mod in SUPPORTED_MODELS:
                print(f"- {mod}")
            sys.exit(1)

        self.rag = rag
        self.rag_config = dict(
            nmax=rag_nb_qry,
            threshold=rag_threshold,
        )

        msg_system("Loading model", model.capitalize())
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
        if self.rag:
            system_prompt = self.SYSTEM_PROMPT + """
            The user will provide all the available data it has on the matter, and you have to formulate an answer based on this.
            At the end of your answer, you will give the references of the provided data you used to build your answer
            """
        else:
            system_prompt = self.SYSTEM_PROMPT
        self._history = [{"role": "system", "content": system_prompt}]
        self._current_prompt_template = self.config["promptTemplate"]

    def token_callback(self, id, token):
        try:
            self.response_buffer.append(token)

            if self.disp_tokens:
                sys.stdout.write(token)
                sys.stdout.flush()
        except KeyboardInterrupt:
            msg_system("Interrupted")
            return False
        except:
            msg_system("Interrupted")
            return False

        return self.continue_token_generation
    
    def ask(self, question, **kwargs):
        if self.rag:
            ressources = self.rag.query_db(question, **self.rag_config)
            prompt = f"{question}\nAvailable data on the subject:\n"
            for (reference, ressource) in ressources:
                prompt += f"At the reference {reference}:\n{ressource}\n\n"
        else:
            prompt = question

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
            set_ai_color()
            response = self.generate(question, callback=self.token_callback, **config)
        except KeyboardInterrupt:
            msg_system("Interrupt\n")
        finally:
            reset_style()
            self.continue_token_generation = False
        print("")
        response = ''.join(self.response_buffer)
        return response

    def conversation(self, **kwargs):
        done = False
        while not done:
            try:
                set_user_color()
                question = input("> ").strip()
                reset_style()
            except KeyboardInterrupt:
                msg_system("Stopping\n")
                break

            if len(question) == 0:
                continue

            if question.startswith("/"):
                done = self.dispatch_command(question[1:])
                continue

            self.ask(question, **kwargs)

        if len(self._history) == 1:    # No more than the first system prompt
            return

        # TODO    Generate the filename with the first question asked only
        #         Move the generation process to a totally different class with its model
        msg_system("Generating a filename for this conversation")
        filename = self.generate_filename()
        msg_system(f"Saving under filename {filename}")
        with open(os.path.join(self.chat_dir, filename), "w") as f:
            for line in self.current_chat_session:
                if line["role"] == "user":
                    if line["content"] == self.FILENAME_GENERATION_PROMPT:
                        break
                    f.write("USER> " + line["content"] + "\n\n")
                elif line["role"] == "assistant":
                    f.write("AI> " + line["content"] + "\n\n")

    def dispatch_command(self, cmd):
        if cmd == "quit":
            msg_system("Stopping\n")
            return True
        # TODO    Command to set the filename of the chat
        # TODO    Command to ask for more creativity in the answer
        # TODO    Command to regenerate a different answer
        # TODO    Help command

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
                msg_system(f"Invalid JSON generated: {err}")

            ntry += 1
        return filename

def env_var_or_exit(var, code=1):
    try:
        return os.environ[var]
    except KeyError:
        print(f"Environment variable {var} not set")
        sys.exit(code)

def main():
    import argparse
    import multiprocessing as mproc

    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", "-v", action="count", help="Turn on verbose output")
    parser.add_argument("--rag", "-r", action="store_true", help="Enable the RAG knowledge retrieval")
    parser.add_argument("--build-rag", action="store_true", help="Build the knowledgebase")
    parser.add_argument("--nb-jobs", "-j",
        type=int,
        default=mproc.cpu_count(),
        help="Number of threads to spawn for the inference",
    )
    parser.add_argument("--filter", "-f", help="Filter the RAG documents to search from", default="")

    parser.add_argument("--llm-temp", "-lt", help="Temperature of the LLM inference", default=0.85, type=float)
    parser.add_argument("--llm-topk", "-lk", help="Top K parameter of the LLM inference", default=40, type=int)
    parser.add_argument("--llm-topp", "-lp", help="Top P parameter of the LLM inference", default=0.4, type=float)
    parser.add_argument("--llm-repeat-penalty", "-lr", help="Repeat penalty of the LLM inference", default=1.18, type=float)
    parser.add_argument("--llm-repeat-last-n", "-lrn", help="Repeat last N parameter of the LLM inference", default=64, type=int)
    parser.add_argument("question", nargs="*", help="Question to ask directly to Aicha")
    args = parser.parse_args()
    set_verbosity(args.verbose)

    llm_cfg = dict(
        temp=args.llm_temp,
        top_k=args.llm_topk,
        top_p = args.llm_topp,
        repeat_penalty = args.llm_repeat_penalty,
        repeat_last_n = args.llm_repeat_last_n,
    )

    model = env_var_or_exit("AICHA_MODEL")
    model_dir = env_var_or_exit("AICHA_MODEL_DIR")
    chathist_dir = env_var_or_exit("AICHA_CHATHIST_DIR")

    if args.rag or args.build_rag:
        rag_dir = env_var_or_exit("AICHA_RAG_KNOWLEDGE_CACHE_DIR")
        rag_target = env_var_or_exit("AICHA_RAG_KNOWLEDGE_DIR")
        rag = KnowledgeLibrary(
            rag_dir,
            rag_target,
            model_dir,
            njobs=args.nb_jobs,
            fpath_filter=args.filter,
            do_not_build=(not args.build_rag),
        )
        if args.build_rag:
            sys.exit(0)            
    else:
        rag = None

    aicha = Aicha(
        model,
        model_dir,
        chathist_dir,
        rag,
    )

    if len(args.question) > 0:
        aicha.ask(" ".join(args.question), **llm_cfg)
    else:
        aicha.conversation(**llm_cfg)

if __name__ == "__main__":
    main()
