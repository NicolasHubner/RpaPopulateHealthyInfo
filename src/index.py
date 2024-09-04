import re
import time
import elastic_transport
from elasticsearch import Elasticsearch, TransportError, helpers
from multiprocessing import Pool

# Configuration
ELASTICSEARCH_HOST = 'localhost'
ELASTICSEARCH_PORT = 9200
SQL_FILE = 'AL_SIH_COMPILADO.sql'
INDEX_NAME = 'index_alagoas'
CHUNK_SIZE = 5000  # Adjust the chunk size for bulk indexing

# Columns to watch (adjust column names as needed)
COLUMNS_TO_WATCH = [
    'Estado', 'Ano', 'Mes', 'Especialidade', 'CNPJ',
    'AIH', 'Procedimento', 'Valor_Total', 'Natureza', 'Dias_Permanência'
]

# Elasticsearch connection
es = Elasticsearch(
    ["http://localhost:9200"],
    basic_auth=("elastic", "<ES_PASSWORD>"),
).options(request_timeout=60)

# Create index with the correct mapping if it doesn't exist
if not es.indices.exists(index=INDEX_NAME):
    es.indices.create(index=INDEX_NAME, body={
        "mappings": {
            "properties": {
                "Estado": {"type": "keyword"},
                "Ano": {"type": "integer"},
                "Mes": {"type": "integer"},
                "Especialidade": {"type": "keyword"},
                "CNPJ": {"type": "keyword"},
                "AIH": {"type": "keyword"},
                "Procedimento": {"type": "keyword"},
                "Valor_Total": {"type": "float"},  # Specify as float
                "Natureza": {"type": "keyword"},
                "Dias_Permanência": {"type": "integer"}
            }
        }
    })

def extract_data(sql_file, chunk_size=CHUNK_SIZE):
    """Extracts data from SQL INSERT statements in chunks."""
    with open(sql_file, 'r') as f:
        data_chunk = []
        for line in f:
            if line.strip().startswith("INSERT INTO"):
                try:
                    # Correctly handle values with different types
                    values_str = re.search(r"VALUES\s*\((.*?)\);", line).group(1)
                    values = re.split(r",\s*(?![^()]*\))", values_str)  # Split correctly, considering commas
                    values = [v.strip().strip("'") for v in values]  # Strip quotes and whitespace
                    # Convert numeric fields to their appropriate types
                    for i, column in enumerate(COLUMNS_TO_WATCH):
                        if column in ['Valor_Total', 'Ano', 'Mes', 'Dias_Permanência']:
                            values[i] = float(values[i]) if '.' in values[i] else int(values[i])
                        # Standardize Especialidade to always have two digits
                        if column == 'Especialidade':
                            values[i] = values[i].zfill(2)  # Pad with zeros if needed
                    data_chunk.append(values)
                    if len(data_chunk) >= chunk_size:
                        yield data_chunk
                        data_chunk = []  # Reset chunk
                except Exception as e:
                    print(f"Error processing line: {line}")
                    print(f"Exception: {e}")
        if data_chunk:  # Yield the last chunk if it exists
            yield data_chunk


def generate_bulk_actions(data_chunk, index_name):
    """Generates bulk actions for Elasticsearch."""
    for row in data_chunk:
        document = dict(zip(COLUMNS_TO_WATCH, row))
        yield {
            "_index": index_name,
            "_source": document
        }

def process_chunk(data_chunk):
    """Indexes a chunk of data into Elasticsearch with retries."""
    actions = generate_bulk_actions(data_chunk, INDEX_NAME)
    for _ in range(3):  # Retry up to 3 times
        try:
            helpers.bulk(es, actions, chunk_size=CHUNK_SIZE)
            break  # Exit loop if successful
        except elastic_transport.ConnectionTimeout:
            time.sleep(5)  # Wait for 5 seconds before retrying
        except TransportError as e:
            print(f"TransportError: {e}")
            time.sleep(5)  # Wait for 5 seconds before retrying

def parallel_bulk_index(sql_file, index_name, num_processes=8):
    """Extracts data, splits it into chunks, and indexes using multiprocessing."""
    start_time = time.time()

    with Pool(processes=num_processes) as pool:
        for data_chunk in extract_data(sql_file):
            pool.map(process_chunk, [data_chunk])  # Process each chunk

    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Data extraction and indexing took: {elapsed_time:.2f} seconds")

# Run the parallel bulk indexing
parallel_bulk_index(SQL_FILE, INDEX_NAME)
