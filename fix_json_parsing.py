# Fix for SmolVLM JSON parsing
# Replace the query_smolvlm function in the notebook with this improved version

def query_smolvlm_improved(image: Image.Image, prompt: str, config: SmolVLMConfig) -> Dict:
    """
    Query SmolVLM with image and prompt (IMPROVED JSON PARSING)

    Args:
        image: PIL Image
        prompt: Text prompt
        config: Model configuration

    Returns:
        Parsed JSON response or error dict
    """
    try:
        # Prepare inputs
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image"},
                    {"type": "text", "text": prompt}
                ]
            }
        ]

        # Process with SmolVLM
        prompt_text = processor.apply_chat_template(messages, add_generation_prompt=True)
        inputs = processor(
            text=prompt_text,
            images=[image],
            return_tensors="pt"
        ).to(config.device)

        # Generate response
        with torch.no_grad():
            generated_ids = model.generate(
                **inputs,
                max_new_tokens=config.max_new_tokens,
                # temperature=config.temperature,  # Remove if model doesn't support
                do_sample=config.do_sample
            )

        # Decode response
        generated_texts = processor.batch_decode(
            generated_ids,
            skip_special_tokens=True
        )

        response_text = generated_texts[0]

        # IMPROVED: Extract JSON more carefully
        # Try multiple strategies to extract valid JSON

        # Strategy 1: Find first { and extract until we have valid JSON
        start_idx = response_text.find('{')
        if start_idx == -1:
            return {"error": "No JSON found in response", "raw_response": response_text}

        # Try parsing progressively longer substrings
        for end_idx in range(start_idx + 10, len(response_text) + 1):
            if response_text[end_idx - 1] == '}':
                try:
                    json_text = response_text[start_idx:end_idx]
                    result = json.loads(json_text)
                    return result  # Success!
                except json.JSONDecodeError:
                    continue  # Try next closing brace

        # Strategy 2: If that fails, try extracting just the first complete JSON object
        try:
            # Find all { } pairs
            stack = []
            for i, char in enumerate(response_text[start_idx:], start=start_idx):
                if char == '{':
                    stack.append(i)
                elif char == '}':
                    if stack:
                        stack.pop()
                        if not stack:  # Found complete JSON object
                            json_text = response_text[start_idx:i+1]
                            result = json.loads(json_text)
                            return result
        except:
            pass

        # Strategy 3: Last resort - try to fix common issues
        try:
            # Extract text between first { and last }
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}')
            if start_idx != -1 and end_idx != -1:
                json_text = response_text[start_idx:end_idx+1]

                # Try to clean up common issues
                json_text = json_text.replace('\n', ' ')  # Remove newlines
                json_text = json_text.replace('\\', '\\\\')  # Escape backslashes

                result = json.loads(json_text)
                return result
        except:
            pass

        # All strategies failed
        return {
            "error": "Could not parse JSON from response",
            "raw_response": response_text[:500]  # First 500 chars for debugging
        }

    except Exception as e:
        return {"error": f"Inference error: {str(e)}"}


# INSTRUCTIONS FOR NOTEBOOK:
# Replace the query_smolvlm function (around line 230) with query_smolvlm_improved
# And remove the temperature parameter from generate() call if you get the warning

print("""
Copy this improved function to replace query_smolvlm in the notebook.

Key improvements:
1. Tries multiple JSON extraction strategies
2. Finds first complete JSON object (stops at first valid parse)
3. Handles extra text after JSON
4. Better error messages with raw response preview
5. Removes temperature parameter (causing warning)
""")
