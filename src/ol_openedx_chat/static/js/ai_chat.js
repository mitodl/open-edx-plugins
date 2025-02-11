(function ($){
    function AiChatAsideView(runtime, element, block_element, init_args) {
        $(function($) {
            const INITIAL_MESSAGES = [
              {
                content: "Hi! What are you interested in learning about?",
                role: "assistant",
              },
            ]

            const STARTERS = init_args.starters
            const REQUEST_OPTS = {
              apiUrl: "https://learn-ai-qa.ol.mit.edu/http/recommendation_agent/",
              transformBody(messages) {
                const message = messages[messages.length - 1].content
                return { message }
              },
            }
            const el = document.getElementById(`app-root-${init_args.block_usage_key}`)
            aiChat.aiChat({
                root: el,
                initialMessages: INITIAL_MESSAGES,
                conversationStarters: STARTERS,
                requestOpts: REQUEST_OPTS,
                className: `ai-chat-${init_args.block_usage_key}`,
            })
            console.log(init_args.starters)
            console.log(init_args.block_usage_key)
            console.log(init_args.user_id)
            console.log(init_args.video_transcript)
        });
    }

    function AiChatAside(runtime, element, block_element, init_args) {
        return new AiChatAsideView(runtime, element, block_element, init_args);
    }

    window.AiChatAsideInit = AiChatAside;
}($));
