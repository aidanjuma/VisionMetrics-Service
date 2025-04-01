from marshmallow import Schema, fields, post_load


class TestSession:
    def __init__(self, session_id: int, is_active: bool):
        self.session_id = session_id
        self.is_active = 1 if is_active else 0

    def __repr__(self):
        return f'<TestSession(session_id={self.session_id}, is_active={self.is_active})>'


class TestSessionSchema(Schema):
    session_id = fields.Integer(required=True)
    is_active = fields.Integer(required=True)

    @post_load
    def make_test_session(self, data, **kwargs):
        return TestSession(**data)
