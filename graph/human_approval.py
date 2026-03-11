from langgraph.checkpoint.sqlite import SqliteSaver

def get_checkpointer():
    """
    SQLite checkpointer: saves full graph state to a local DB file.
    This is what makes interrupt() work — state survives between runs.
    """
    return SqliteSaver.from_conn_string("checkpoints.db")