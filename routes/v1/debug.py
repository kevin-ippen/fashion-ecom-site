from fastapi import APIRouter
from databricks.sdk import WorkspaceClient
from core.config import settings

router = APIRouter(prefix="/debug", tags=["debug"])

@router.get("/test-query/{product_id}")
async def test_query(product_id: str):
    """Test query directly"""
    w = WorkspaceClient()

    query = f"""
    SELECT COUNT(*) as count
    FROM main.fashion_sota.outfit_recommendations_from_lookbook
    WHERE product_1_id = '{product_id}'
    """

    execution = w.statement_execution.execute_statement(
        statement=query,
        warehouse_id=settings.SQL_WAREHOUSE_ID
    )
    result = execution.result
    
    return {
        "has_result": result is not None,
        "has_data_array": hasattr(result, 'data_array') if result else False,
        "data_array_length": len(result.data_array) if (result and hasattr(result, 'data_array') and result.data_array) else 0,
        "data": result.data_array[0] if (result and result.data_array) else None
    }

