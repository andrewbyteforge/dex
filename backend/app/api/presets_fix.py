"""
Quick fix for the presets API delete endpoint issue.

Replace the problematic delete endpoint in presets.py
"""

# Find this in your presets.py file and replace it:

# BEFORE (causing the error):
# @router.delete("/{preset_id}", status_code=status.HTTP_204_NO_CONTENT)
# async def delete_preset(preset_id: str) -> None:

# AFTER (fixed version):
@router.delete("/{preset_id}")
async def delete_preset(preset_id: str) -> Dict[str, str]:
    """
    Delete a custom preset.
    
    Args:
        preset_id: Preset identifier
        
    Returns:
        Success message
    """
    logger.info(f"Deleting preset: {preset_id}")
    
    # Check if preset exists and is custom
    if preset_id not in _custom_presets:
        built_in_presets = _get_built_in_presets()
        if preset_id in built_in_presets:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete built-in preset"
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preset '{preset_id}' not found"
        )
    
    # Delete preset
    del _custom_presets[preset_id]
    
    logger.info(f"Deleted preset: {preset_id}")
    
    # Return a response body (required when not using 204)
    return {"message": f"Preset {preset_id} deleted successfully"}