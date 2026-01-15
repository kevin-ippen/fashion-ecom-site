"""
Submit SmolVLM attribute extraction job to Databricks

Requires environment variables:
- DATABRICKS_NOTEBOOK_PATH: Path to notebook in workspace (e.g., /Users/user@example.com/notebook_name)
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.jobs import Task, NotebookTask, Source
from databricks.sdk.service.compute import AutoScale

print("=" * 80)
print("SmolVLM Attribute Extraction - Job Submission")
print("=" * 80)

# Initialize Databricks client
print("\n🔄 Initializing Databricks workspace client...")
w = WorkspaceClient()
print(f"✅ Connected to: {w.config.host}")

# Configuration (from environment)
NOTEBOOK_PATH = os.getenv("DATABRICKS_NOTEBOOK_PATH", "")
if not NOTEBOOK_PATH:
    # Default to user's home folder in workspace
    user_email = os.getenv("DATABRICKS_USER", "")
    if user_email:
        NOTEBOOK_PATH = f"/Users/{user_email}/smolvlm_batch_attribute_extraction"
    else:
        print("Error: DATABRICKS_NOTEBOOK_PATH or DATABRICKS_USER environment variable required")
        sys.exit(1)

NOTEBOOK_SOURCE = Path(__file__).parent.parent / "notebooks" / "smolvlm_batch_attribute_extraction.py"

print(f"\n📝 Notebook Configuration:")
print(f"   Source: {NOTEBOOK_SOURCE}")
print(f"   Target: {NOTEBOOK_PATH}")

# Upload notebook to workspace
print("\n🔄 Uploading notebook to workspace...")
try:
    notebook_content = NOTEBOOK_SOURCE.read_text()

    # Import notebook (this will create or update it)
    w.workspace.import_(
        path=NOTEBOOK_PATH,
        format="SOURCE",
        language="PYTHON",
        content=notebook_content.encode('utf-8'),
        overwrite=True
    )
    print(f"✅ Notebook uploaded successfully")
except Exception as e:
    print(f"❌ Error uploading notebook: {e}")
    sys.exit(1)

# Create job configuration
print("\n🔄 Creating job configuration...")

job_config = {
    "name": "SmolVLM Attribute Extraction - Test (100 products)",
    "tasks": [
        Task(
            task_key="extract_visual_attributes",
            description="Extract visual attributes from 100 product images using SmolVLM-2.2B",
            notebook_task=NotebookTask(
                notebook_path=NOTEBOOK_PATH,
                source=Source.WORKSPACE
            ),
            new_cluster={
                "spark_version": "14.3.x-gpu-ml-scala2.12",
                "node_type_id": "g5.xlarge",  # NVIDIA A10G GPU
                "num_workers": 0,  # Single node for test
                "spark_conf": {
                    "spark.databricks.cluster.profile": "singleNode",
                    "spark.master": "local[*]"
                },
                "custom_tags": {
                    "ResourceClass": "SingleNode",
                    "Project": "SmolVLM-Extraction",
                    "Environment": "Test"
                }
            },
            timeout_seconds=7200,  # 2 hour timeout
            max_retries=0  # No retries for testing
        )
    ],
    "max_concurrent_runs": 1,
    "timeout_seconds": 7200
}

print("✅ Job configuration created:")
print(f"   Cluster: g5.xlarge (Single Node, GPU)")
print(f"   Runtime: 14.3.x GPU ML")
print(f"   Timeout: 2 hours")

# Create the job
print("\n🔄 Creating job in Databricks...")
try:
    job = w.jobs.create(**job_config)
    job_id = job.job_id
    print(f"✅ Job created successfully")
    print(f"   Job ID: {job_id}")
    print(f"   Job URL: {w.config.host}/#job/{job_id}")
except Exception as e:
    print(f"❌ Error creating job: {e}")
    sys.exit(1)

# Submit the job
print("\n🚀 Submitting job run...")
try:
    run = w.jobs.run_now(job_id=job_id)
    run_id = run.run_id
    print(f"✅ Job submitted successfully")
    print(f"   Run ID: {run_id}")
    print(f"   Run URL: {w.config.host}/#job/{job_id}/run/{run_id}")
except Exception as e:
    print(f"❌ Error submitting job: {e}")
    sys.exit(1)

print("\n" + "=" * 80)
print("JOB SUBMITTED SUCCESSFULLY")
print("=" * 80)
print(f"\n📊 Monitoring Information:")
print(f"   Job ID: {job_id}")
print(f"   Run ID: {run_id}")
print(f"\n🔗 URLs:")
print(f"   Job: {w.config.host}/#job/{job_id}")
print(f"   Run: {w.config.host}/#job/{job_id}/run/{run_id}")

print(f"\n⏱️  Expected Duration: 15-20 minutes")
print(f"💰 Expected Cost: ~$1-2")

print("\n📈 What's Happening:")
print("   1. Cluster starting (~5 min)")
print("   2. Installing dependencies (~2 min)")
print("   3. Loading SmolVLM-2.2B (~3 min)")
print("   4. Processing 100 products (~8-12 min)")
print("   5. Quality analysis (instant)")

print("\n🔍 Monitor Progress:")
print(f"   - Open Run URL above")
print(f"   - Watch notebook cells execute")
print(f"   - Check 'Quality Analysis' section for results")

# Monitor job progress
print("\n🔄 Monitoring job status (will check every 30 seconds)...")
print("   Press Ctrl+C to stop monitoring (job will continue running)")

try:
    while True:
        run_status = w.jobs.get_run(run_id=run_id)
        state = run_status.state.life_cycle_state.value

        if state in ["PENDING", "RUNNING"]:
            state_message = run_status.state.state_message or "No message"
            print(f"   Status: {state} - {state_message}")
            time.sleep(30)
        elif state == "TERMINATED":
            result = run_status.state.result_state.value
            if result == "SUCCESS":
                print(f"\n✅ JOB COMPLETED SUCCESSFULLY!")
                print(f"\n📊 Next Steps:")
                print(f"   1. Review results in notebook output")
                print(f"   2. Check success rate (target: >85%)")
                print(f"   3. Review extracted attributes")
                print(f"   4. Run validation queries")
                print(f"\n📋 Tables Created:")
                print(f"   - main.fashion_demo.product_extracted_attributes")
                print(f"   - main.fashion_demo.products_enriched_descriptions")
                break
            else:
                print(f"\n❌ Job failed with result: {result}")
                print(f"   Error: {run_status.state.state_message}")
                break
        else:
            print(f"\n⚠️  Unexpected state: {state}")
            break

except KeyboardInterrupt:
    print("\n\n⚠️  Monitoring stopped (job continues running in background)")
    print(f"   Check status at: {w.config.host}/#job/{job_id}/run/{run_id}")

print("\n" + "=" * 80)
