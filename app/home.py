import streamlit as st
from streamlit.components.v1 import html

from config import vector_cfg
from functions_llm_request import LLM_request


index_path = vector_cfg['INDEX_PATH']

st.title('AIDoc')
user_query = st.text_area('Enter code snippet:')

if st.button('Ask.'):
    if user_query:
        response = LLM_request(query=user_query, index_path=index_path)
        st.write(response)
    else:
        st.write('Type a request.')

