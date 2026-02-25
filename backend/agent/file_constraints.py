from agent.state import GeneratedFile

NEXT_CONFIG_MJS_CONTENT = """const nextConfig = {};
export default nextConfig;
"""


def enforce_nextjs_config_filename(
    generated_files: dict[str, GeneratedFile],
    template_name: str,
) -> tuple[dict[str, GeneratedFile], bool]:
    """Normalize Next.js config filename to next.config.mjs."""
    if template_name != "nextjs" or "next.config.ts" not in generated_files:
        return generated_files, False

    updated = dict(generated_files)
    ts_entry = updated.pop("next.config.ts", {})

    updated["next.config.mjs"] = GeneratedFile(
        file_path="next.config.mjs",
        file_contents=NEXT_CONFIG_MJS_CONTENT,
        language="javascript",
        phase_index=ts_entry.get("phase_index", 0),
    )
    return updated, True
