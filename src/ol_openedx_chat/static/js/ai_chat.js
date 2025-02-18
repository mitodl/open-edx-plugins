(function ($) {
  function AiChatAsideView(runtime, element, block_element, init_args) {
    $(function ($) {
      const INITIAL_MESSAGES = [
        {
          content: "Hi! What are you interested in learning about?",
          role: "assistant",
        },
      ];

      const STARTERS = init_args.starters;
      $(".ai-chat-button").on("click", function () {
        const blockKey = $(this).data("block-key");
        window.parent.postMessage(
          {
            type: "smoot-design::chat-open",
            payload: {
              askTimTitle: `for help with ${blockKey}`,
              apiUrl:
                "http://ai.open.odl.local:8002/http/recommendation_agent/",
              initialMessages: INITIAL_MESSAGES,
              conversationStarters: STARTERS,
            },
          },
          "http://apps.local.openedx.io:2000", // Ensure correct parent origin
        );
      });
      console.log(init_args.starters);
      console.log(init_args.block_usage_key);
      console.log(init_args.user_id);
      console.log(init_args.video_transcript);
    });
  }

  function AiChatAside(runtime, element, block_element, init_args) {
    return new AiChatAsideView(runtime, element, block_element, init_args);
  }

  window.AiChatAsideInit = AiChatAside;
})($);
