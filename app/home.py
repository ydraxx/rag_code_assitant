import streamlit as st
from streamlit.components.v1 import html

from functions_llm_request import LLM_request


st.title('AIDoc')
user_query = st.text_area('Enter code snippet:')

if st.button('Ask.'):
    if user_query:
        response = LLM_request(query=user_query)
        st.write
    else:
        st.write('Type a request.')
