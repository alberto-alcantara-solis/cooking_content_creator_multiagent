import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver

def get_checkpointer():
    """
    SQLite checkpointer: saves full graph state to a local DB file.
    This is what makes interrupt() work — state survives between runs.
    """
    conn = sqlite3.connect("checkpoints.db", check_same_thread=False)
    return SqliteSaver(conn)