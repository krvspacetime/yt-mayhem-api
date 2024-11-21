from pydantic import BaseModel


class AddCommentRequest(BaseModel):
    video_id: str
    comment_text: str
