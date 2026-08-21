from typing import Literal


Language = Literal["CN", "US"]
MessageKey = Literal[
    "artifact_upload_failed",
    "empty_result",
    "file_instructions_required",
    "processing_failed",
    "too_many_attachments",
]


_KOOK_MESSAGES: dict[Language, dict[MessageKey, str]] = {
    "CN": {
        "artifact_upload_failed": "文件 {name} 上传失败，请稍后重试。",
        "empty_result": "任务已完成，但没有生成文字结果。",
        "file_instructions_required": "已收到文件，请告诉我，希望我应该如何处理。",
        "processing_failed": "处理失败，请稍后重试。",
        "too_many_attachments": "**{version}** 当前版本每次只能处理一个文件，请重新发送。",
    },
    "US": {
        "artifact_upload_failed": "Failed to upload {name}. Please try again later.",
        "empty_result": "The task completed without producing a text response.",
        "file_instructions_required": "File received. Please tell me how you would like it processed.",
        "processing_failed": "Processing failed. Please try again later.",
        "too_many_attachments": "**{version}** Only one file can be processed at a time. Please send the files separately.",
    },
}


def kook_message(language: Language, key: MessageKey, **values: str) -> str:
    """Render a localized message intended for a KOOK user.

    Args:
        language: Language used for the rendered message.
        key: Identifier of the message template to render.
        **values: Values interpolated into the selected message template.

    Returns:
        The localized and formatted message.
    """
    return _KOOK_MESSAGES[language][key].format(**values)
