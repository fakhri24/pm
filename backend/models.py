from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field

TITLE_MAX = 500
DETAILS_MAX = 5000

PRIORITY_VALUES = {"low", "medium", "high", "urgent"}


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=6, max_length=200)


class CardOut(BaseModel):
    id: int
    title: str
    details: str
    position: int
    priority: Optional[str] = None
    due_date: Optional[str] = None
    labels: list[str] = []


class ColumnOut(BaseModel):
    id: int
    title: str
    position: int
    cards: list[CardOut]


class BoardOut(BaseModel):
    id: int
    name: str
    columns: list[ColumnOut]


class BoardSummary(BaseModel):
    id: int
    name: str
    card_count: int


class RenameColumnRequest(BaseModel):
    title: str = Field(max_length=TITLE_MAX)


class CreateColumnRequest(BaseModel):
    title: str = Field(max_length=TITLE_MAX)


class CreateBoardRequest(BaseModel):
    name: str = Field(min_length=1, max_length=TITLE_MAX)
    template: str = "kanban"


class RenameBoardRequest(BaseModel):
    name: str = Field(min_length=1, max_length=TITLE_MAX)


class CreateCardRequest(BaseModel):
    column_id: int
    title: str = Field(max_length=TITLE_MAX)
    details: str = Field(default="", max_length=DETAILS_MAX)
    priority: Optional[str] = Field(default=None)
    due_date: Optional[str] = Field(default=None)
    labels: list[str] = []


class UpdateCardRequest(BaseModel):
    title: str = Field(max_length=TITLE_MAX)
    details: str = Field(max_length=DETAILS_MAX)
    priority: Optional[str] = Field(default=None)
    due_date: Optional[str] = Field(default=None)
    labels: list[str] = []


class MoveCardRequest(BaseModel):
    column_id: int
    position: int = Field(ge=0)


class MoveColumnRequest(BaseModel):
    position: int = Field(ge=0)


class CommentOut(BaseModel):
    id: int
    card_id: int
    content: str
    created_at: str


class CreateCommentRequest(BaseModel):
    content: str = Field(min_length=1, max_length=DETAILS_MAX)


class ChecklistItemOut(BaseModel):
    id: int
    card_id: int
    content: str
    checked: bool
    position: int


class CreateChecklistItemRequest(BaseModel):
    content: str = Field(min_length=1, max_length=TITLE_MAX)


class UpdateChecklistItemRequest(BaseModel):
    content: Optional[str] = Field(default=None, max_length=TITLE_MAX)
    checked: Optional[bool] = None


class ArchivedCardOut(BaseModel):
    id: int
    title: str
    details: str
    priority: Optional[str] = None
    due_date: Optional[str] = None
    labels: list[str] = []
    column_id: int
    column_title: str


class ActivityEntry(BaseModel):
    id: int
    board_id: int
    username: str
    action: str
    description: str
    created_at: str


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=DETAILS_MAX)


class ChatRequest(BaseModel):
    message: str = Field(max_length=DETAILS_MAX)
    history: list[ChatMessage] = []


# --- AI board update actions ---

class CreateCardAction(BaseModel):
    action: Literal["create_card"]
    column_id: int
    title: str = Field(max_length=TITLE_MAX)
    details: str = Field(default="", max_length=DETAILS_MAX)
    priority: Optional[str] = None
    due_date: Optional[str] = None
    labels: list[str] = []


class UpdateCardAction(BaseModel):
    """Partial update: only fields the model includes are changed."""
    action: Literal["update_card"]
    card_id: int
    title: Optional[str] = Field(default=None, max_length=TITLE_MAX)
    details: Optional[str] = Field(default=None, max_length=DETAILS_MAX)
    priority: Optional[str] = None
    due_date: Optional[str] = None
    labels: Optional[list[str]] = None


class DeleteCardAction(BaseModel):
    action: Literal["delete_card"]
    card_id: int


class MoveCardAction(BaseModel):
    action: Literal["move_card"]
    card_id: int
    column_id: int
    position: int = Field(ge=0)


class RenameColumnAction(BaseModel):
    action: Literal["rename_column"]
    column_id: int
    title: str = Field(max_length=TITLE_MAX)


BoardAction = Annotated[
    Union[
        CreateCardAction,
        UpdateCardAction,
        DeleteCardAction,
        MoveCardAction,
        RenameColumnAction,
    ],
    Field(discriminator="action"),
]
