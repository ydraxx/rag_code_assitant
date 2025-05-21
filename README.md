# RAG C++ project assistant



## Documentation

### Functionning

- Run the LLM
```
ollama serve
```

- Choose your model
```
ollama pull <model_name>
```

- Launch the interface
```
streamlit run app/home.py
```

### Building

- Setup config file

Create app/config.py file.
```
vector_cfg = {
    "INDEX_PATH": "",
    "JSON_PATH": "",
    "DOCS_PATH": "",
}

parser_cfg = {

}

llm_cfg = {
    "MODEL_NAME": "",
    "HOST": "http://localhost:11434"
}
```

- Build the vectorstore
```
python3 functions_vectorstore.py
```
