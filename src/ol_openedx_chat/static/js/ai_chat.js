(function ($){
    function AiChatAsideView(runtime, element, block_element, init_args) {
        $(function($) {
            console.log("INSIDE AiChatAsideView")
            const INITIAL_MESSAGES = [
              {
                content: "Hi! What are you interested in learning about?",
                role: "assistant",
              },
            ]

            const STARTERS = init_args.starters

            const REQUEST_OPTS = {
              apiUrl: "http://ai.open.odl.local:8002/http/recommendation_agent/",
              transformBody(messages) {
                const message = messages[messages.length - 1].content
                return { message }
              },
            }
            console.log(`app-root-${init_args.block_usage_key}`)
            const el = document.getElementById(`app-root-${init_args.block_usage_key}`)
            console.log(el)
            aiChat.aiChat({
                root: el,
                initialMessages: INITIAL_MESSAGES,
                conversationStarters: STARTERS,
                requestOpts: REQUEST_OPTS,
                className: `ai-chat-${init_args.block_usage_key}`,
            })
            console.log(init_args)
        });
    }

    function AiChatAside(runtime, element, block_element, init_args) {
        return new AiChatAsideView(runtime, element, block_element, init_args);
    }

    window.AiChatAsideInit = AiChatAside;
}($));
