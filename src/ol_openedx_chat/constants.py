# The dictionary should contain all the block types for which the chat should be
# applicable if a block has sub-blocks or sub category, that should be added in the list
VIDEO_BLOCK_CATEGORY = "video"
PROBLEM_BLOCK_CATEGORY = "problem"

# The actual chat URL is `https://api-learn-ai.ol.mit.edu/http/video_gpt_agent/`
# for video blocks and`https://api-learn-ai.ol.mit.edu/http/tutor_agent/`
# for problem blocks.
MIT_AI_CHAT_URL_PATHS = {
    VIDEO_BLOCK_CATEGORY: "http/video_gpt_agent/",
    PROBLEM_BLOCK_CATEGORY: "http/tutor_agent/",
}

BLOCK_TYPE_TO_SETTINGS = {
    VIDEO_BLOCK_CATEGORY: "ENABLE_VIDEOGPT_FOR_VIDEO_BLOCK",
    PROBLEM_BLOCK_CATEGORY: "ENABLE_AI_TUTOR_FOR_PROBLEM_BLOCK",
}

CHAT_APPLICABLE_BLOCKS = [PROBLEM_BLOCK_CATEGORY, VIDEO_BLOCK_CATEGORY]

ENGLISH_LANGUAGE_TRANSCRIPT = "en"
