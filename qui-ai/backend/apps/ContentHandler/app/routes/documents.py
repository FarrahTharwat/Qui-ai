from app.utils.ProcessAndGenerate import process_pdf_pipeline_fixed


async def process_document_async(session_id: str, pdf_path: str, document_service):
    """
    Updated document processing that saves cleaned text in session data
    """
    try:
        redis_manager = get_redis_manager()

        # Set initial processing status
        redis_manager.set_session_status(session_id, "processing", {
            "message": "Processing document...",
            "progress": 10,
            "filename": os.path.basename(pdf_path)
        })

        # Process the PDF using your existing pipeline
        result = process_pdf_pipeline_fixed(
            pdf_path=pdf_path,
            output_dir=f"static/output/{session_id}",
            session_id=session_id,
            save_json=True,
            generate_pdf_output=True
        )

        if result.get("success"):
            # Store cleaned text and results in Redis
            redis_manager.set_session_status(session_id, "cleaned", {
                "message": "Document cleaned successfully",
                "progress": 100,
                "cleaned_text": result.get("cleaned_text", ""),
                "polished_text": result.get("polished_text", ""),
                "pdf_path": result.get("pdf_path"),
                "json_path": result.get("json_path"),
                "filename": os.path.basename(pdf_path),
                "ready_for_mcq": True,
                "completed_at": datetime.now().isoformat()
            })

            logger.info(f"Document processing completed for session {session_id}")
        else:
            # Handle processing failure
            redis_manager.set_session_status(session_id, "failed", {
                "error": result.get("error", "Unknown processing error"),
                "failed_at": datetime.now().isoformat()
            })

    except Exception as e:
        logger.error(f"Document processing failed for session {session_id}: {e}")
        redis_manager = get_redis_manager()
        redis_manager.set_session_status(session_id, "failed", {
            "error": str(e),
            "failed_at": datetime.now().isoformat()
        })