import streamlit as st
from streamlit.components.v1 import html


st.title('AIDoc')
user_query = st.text_area('Enter code snippet:')

if st.button('Ask.'):
    if user_query:
        response = LLM_request(user_query)
        st.write
    else:
        st.write('Type a request.')