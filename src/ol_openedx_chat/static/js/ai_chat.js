(function ($) {
  function AiChatAsideView(runtime, element, block_element, init_args) {
    $(function ($) {

      const INITIAL_MESSAGES = [
        {
          content: "Hi! What are you interested in learning about?",
          role: "assistant",
        },
      ];
      $(`#chat-button-${init_args.block_usage_key}`).on("click", { starters: init_args.starters, askTimTitle: init_args.ask_tim_drawer_title }, function (event) {
        const starters = event.data.starters.map(message => ({ content: message }));

        window.parent.postMessage(
          {
            type: "smoot-design::chat-open",
            payload: {
              askTimTitle: event.data.askTimTitle,
              apiUrl: init_args.learn_ai_api_url,
              initialMessages: INITIAL_MESSAGES,
              conversationStarters: starters,
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
