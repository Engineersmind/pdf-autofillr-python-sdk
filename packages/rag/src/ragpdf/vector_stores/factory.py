from ragpdf.vector_stores.base import VectorStoreBackend


class VectorStoreFactory:
    @staticmethod
    def create() -> VectorStoreBackend:
        from ragpdf.config.settings import (
            PINECONE_API_KEY,
            RAGPDF_AZURE_ACCOUNT,
            RAGPDF_AZURE_CONN_STR,
            RAGPDF_AZURE_CONTAINER,
            RAGPDF_CHROMA_COLLECTION,
            RAGPDF_CHROMA_PATH,
            RAGPDF_DATA_PATH,
            RAGPDF_GCS_BUCKET,
            RAGPDF_GCS_PREFIX,
            RAGPDF_PINECONE_INDEX,
            RAGPDF_PINECONE_NAMESPACE,
            RAGPDF_S3_BUCKET,
            RAGPDF_S3_PREFIX,
            RAGPDF_S3_REGION,
            RAGPDF_VECTOR_STORE,
            RAGPDF_WEAVIATE_API_KEY,
            RAGPDF_WEAVIATE_CLASS,
            RAGPDF_WEAVIATE_URL,
        )

        if RAGPDF_VECTOR_STORE == "s3":
            from ragpdf.vector_stores.s3_vector_store import S3VectorStore

            return S3VectorStore(
                bucket=RAGPDF_S3_BUCKET,
                region=RAGPDF_S3_REGION,
                prefix=RAGPDF_S3_PREFIX,
            )

        if RAGPDF_VECTOR_STORE == "azure":
            # Azure: store vector_database.json in Azure Blob, same flat-JSON logic
            from ragpdf.vector_stores.azure_vector_store import AzureVectorStore

            return AzureVectorStore(
                account=RAGPDF_AZURE_ACCOUNT,
                container=RAGPDF_AZURE_CONTAINER,
                conn_str=RAGPDF_AZURE_CONN_STR,
            )

        if RAGPDF_VECTOR_STORE == "gcs":
            from ragpdf.vector_stores.gcs_vector_store import GCSVectorStore

            return GCSVectorStore(bucket=RAGPDF_GCS_BUCKET, prefix=RAGPDF_GCS_PREFIX)

        if RAGPDF_VECTOR_STORE == "pinecone":
            from ragpdf.vector_stores.pinecone_store import PineconeStore

            return PineconeStore(
                api_key=PINECONE_API_KEY,
                index_name=RAGPDF_PINECONE_INDEX,
                namespace=RAGPDF_PINECONE_NAMESPACE,
            )

        if RAGPDF_VECTOR_STORE == "chroma":
            from ragpdf.vector_stores.chroma_store import ChromaStore

            return ChromaStore(
                path=RAGPDF_CHROMA_PATH, collection=RAGPDF_CHROMA_COLLECTION
            )

        if RAGPDF_VECTOR_STORE == "weaviate":
            from ragpdf.vector_stores.weaviate_store import WeaviateStore

            return WeaviateStore(
                url=RAGPDF_WEAVIATE_URL,
                api_key=RAGPDF_WEAVIATE_API_KEY,
                class_name=RAGPDF_WEAVIATE_CLASS,
            )

        from ragpdf.vector_stores.local_vector_store import LocalVectorStore

        return LocalVectorStore(path=RAGPDF_DATA_PATH)
