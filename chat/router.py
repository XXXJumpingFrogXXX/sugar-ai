from fastapi import APIRouter
from pydantic import BaseModel

from unsloth import FastLanguageModel
import torch

max_seq_length = 2048 # Choose any! We auto support RoPE Scaling internally!
dtype = None # None for auto detection. Float16 for Tesla T4, V100, Bfloat16 for Ampere+
load_in_4bit = True # Use 4bit quantization to reduce memory usage. Can be False.

alpaca_prompt = """Below is an instruction that describes a task, along with an input that provides additional context. Write a response that appropriately completes the request.

### Instruction:
{}

### Input:
{}

### Response:
{}"""

class Question(BaseModel):
    query: str

@router.post("/generate_answer")
def generate_answer(value: Question):
    try:
        llama_model, llama_tokenizer = FastLanguageModel.from_pretrained(
            model_name = "Antonio27/llama3-8b-4-bit-for-sugar",
            max_seq_length = max_seq_length,
            dtype = dtype,
            load_in_4bit = load_in_4bit,
        )

        gemma_model, gemma_tokenizer = FastLanguageModel.from_pretrained(
            model_name = "unsloth/gemma-2-9b-it-bnb-4bit",
            max_seq_length = max_seq_length,
            dtype = dtype,
            load_in_4bit = load_in_4bit,
        )

        FastLanguageModel.for_inference(llama_model)
        llama_tokenizer.pad_token = llama_tokenizer.eos_token
        llama_tokenizer.add_eos_token = True

        inputs = llama_tokenizer(
            [
                alpaca_prompt.format(
                    f'''
                    Your task is to answer children's questions using simple language.
                    Explain any difficult words in a way a 3-year-old can understand.
                    Keep responses under 60 words.
                    \n\nQuestion: {value.query}
                    ''',  # instruction
                    "",  # input
                    "",  # output - leave this blank for generation!
                )
            ], return_tensors="pt").to("cuda")

        outputs = llama_model.generate(**inputs, max_new_tokens=256, temperature=0.6)
        decoded_outputs = llama_tokenizer.batch_decode(outputs)

        response_text = decoded_outputs[0]

        match = re.search(r"### Response:(.*?)(?=\n###|$)", response_text, re.DOTALL)
        if match:
            initial_response = match.group(1).strip()
        else:
            initial_response = ""

        FastLanguageModel.for_inference(gemma_model)
        gemma_tokenizer.pad_token = gemma_tokenizer.eos_token
        gemma_tokenizer.add_eos_token = True

        inputs = gemma_tokenizer(
            [
                alpaca_prompt.format(
                    f'''
                    Modify the given content for a 5-year-old.
                    Use simple words and phrases.
                    Remove any repetitive information.
                    Keep responses under 50 words.
                    \n\nGiven Content: {initial_response}
                    ''',  # instruction
                    "",  # input
                    "",  # output - leave this blank for generation!
                )
            ], return_tensors="pt").to("cuda")

        outputs = gemma_model.generate(**inputs, max_new_tokens=256, temperature=0.6)
        decoded_outputs = gemma_tokenizer.batch_decode(outputs)

        response_text = decoded_outputs[0]

        match = re.search(r"### Response:(.*?)(?=\n###|$)", response_text, re.DOTALL)
        if match:
            adjusted_response = match.group(1).strip()
        else:
            adjusted_response = ""

        return {
            'success': True,
            'response': {
                "result": adjusted_response
            }
        }

    except Exception as e:
        return {'success': False, 'response': str(e)}
    