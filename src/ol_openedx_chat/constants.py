# The dictionary should contain all the block types for which the chat should be
# applicable if a block has sub-blocks or sub category, that should be added in the list
VIDEO_BLOCK_CATEGORY = "video"
PROBLEM_BLOCK_CATEGORY = "problem"
LEARN_AI_CHAT_URL_PATH = {
    VIDEO_BLOCK_CATEGORY: "http/video_gpt_agent/",
    PROBLEM_BLOCK_CATEGORY: "http/tutor_agent/",
}
CHAT_APPLICABLE_BLOCKS = [PROBLEM_BLOCK_CATEGORY, VIDEO_BLOCK_CATEGORY]

ENGLISH_LANGUAGE_TRANSCRIPT = "en"
