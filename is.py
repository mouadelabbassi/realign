from datasets import load_dataset
ds = load_dataset("edinburghcstr/ami", "ihm", split="test[:5]")