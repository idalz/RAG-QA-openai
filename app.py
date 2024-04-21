import os
import tempfile

import streamlit as st

from langchain_openai import ChatOpenAI
from langchain import hub
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.tools.retriever import create_retriever_tool
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
from langchain_community.tools import ArxivQueryRun
from langchain_community.utilities import ArxivAPIWrapper
from langchain.agents import create_openai_tools_agent, AgentExecutor

import dotenv
dotenv.load_dotenv()



def create_agent(pdf_path=None):
    llm = ChatOpenAI(model="gpt-3.5-turbo-1106", temperature=0.2)
    prompt = hub.pull('hwchase17/openai-functions-agent')
    
    loader = PyPDFLoader(pdf_path)
    data = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    docs = text_splitter.split_documents(data)

    st.session_state.vectorstore = Chroma.from_documents(documents=docs, embedding=OpenAIEmbeddings())

    st.session_state.retriever = st.session_state.vectorstore.as_retriever()
    retriever_tool = create_retriever_tool(
        retriever=st.session_state.retriever, 
        name="document_search",
        description="Search for information in the document."
    )

    wiki_wrapper = WikipediaAPIWrapper(
        top_k_results=1,
        doc_content_chars_max=200
    )

    wiki_tool = WikipediaQueryRun(api_wrapper=wiki_wrapper)

    ### Create a arxiv tool
    arxiv_wrapper = ArxivAPIWrapper(
        top_k_results=1,
        doc_content_chars_max=200
    )

    arxiv_tool = ArxivQueryRun(api_wrapper=arxiv_wrapper)

    tools = [retriever_tool, wiki_tool, arxiv_tool]

    agent = create_openai_tools_agent(llm, tools, prompt)

    st.session_state.agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)


st.title('Chat with OpenAI')

question = st.text_input('Ask a question')

if st.button('Ask'):
    if 'agent_executor' not in st.session_state:
        st.error("Please upload a pdf and press read button")
    else:
        if question:
            response = st.session_state.agent_executor.invoke({"input":question})
            st.write(response['output'])
        else:
            st.error("Provide a question")

uploaded_file = st.sidebar.file_uploader("Upload a PDF file", type="pdf")

if st.sidebar.button('Read'):
    if uploaded_file is not None:
        # Delete collection if exists (Created by another pdf)
        if 'vectorstore' in st.session_state:
            st.session_state.vectorstore.delete_collection()
        # Check if an agent exists and delete it
        if 'agent_executor' in st.session_state:
            del st.session_state['agent_executor']
        # Save the uploaded file to a temporary directory
        temp_dir = tempfile.TemporaryDirectory()
        temp_file_path = os.path.join(temp_dir.name, uploaded_file.name)
        with open(temp_file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # Recreate agent with current pdf
        create_agent(temp_file_path)

        # Delete the temporary directory and its contents
        temp_dir.cleanup()
