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
            $('.ai-chat-button').on('click', function () {
                const blockKey = $(this).data("block-key")
                const aiChatRootSelector = '#ai-chat-root-' + blockKey
                window.parent.postMessage(
                    {
                        action: "createAIChat",
                        className: `ai-chat-root`,
                        starters: STARTERS,
                        requestOptsAPIURL: "http://ai.open.odl.local:8002/http/recommendation_agent/",
                        initialMessages: INITIAL_MESSAGES,
                        aiChatRootSelector: aiChatRootSelector
                    },
                    "http://apps.local.openedx.io:2000"  // Ensure correct parent origin
                );
            });
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
