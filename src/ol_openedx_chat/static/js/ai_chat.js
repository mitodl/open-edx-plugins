(function ($) {
  function AiChatAsideView(runtime, element, block_element, init_args) {
    $(function ($) {

      const INITIAL_MESSAGES = [
        {
          content: "Hi! What are you interested in learning about?",
          role: "assistant",
        },
      ];

      const STARTERS = [
        { content: "I'm interested in quantum computing" },
        { content: "I want to understand global warming. " },
        { content: "I am curious about AI applications for business" },
      ]

      $(`#chat-button-${init_args.block_usage_key}`).on("click", { starters: init_args.starters, assistantInitialMessages: init_args.assistant_initial_messages }, function (event) {
        const blockKey = $(this).data("block-key");

        if (event.data.starters.length === 0) {
            event.data.starters = STARTERS;
        } else {
            event.data.starters = event.data.starters.map(message => ({ content: message }));
        }

        if (event.data.assistantInitialMessages.length === 0) {
          event.data.assistantInitialMessages = INITIAL_MESSAGES;
        } else {
          event.data.assistantInitialMessages = event.data.assistantInitialMessages.map(message => ({ content: message, role: "assistant" }));
        }

        window.parent.postMessage(
          {
            type: "smoot-design::chat-open",
            payload: {
              askTimTitle: `for help with ${blockKey}`,
              apiUrl: init_args.learn_ai_api_url,
              initialMessages: event.data.assistantInitialMessages,
              conversationStarters: event.data.starters,
            },
          },
          "http://apps.local.openedx.io:2000", // Ensure correct parent origin
        );
      });
    });
  }

  function AiChatAside(runtime, element, block_element, init_args) {
    return new AiChatAsideView(runtime, element, block_element, init_args);
  }

  window.AiChatAsideInit = AiChatAside;
})($);
