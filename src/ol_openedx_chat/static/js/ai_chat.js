(function ($) {
  function AiChatAsideView(runtime, element, block_element, init_args) {
    $(function ($) {

      const INITIAL_MESSAGES = [
        {
          content: "Hi! Do you need any help?",
          role: "assistant",
        },
      ];

      $(`#chat-button-${init_args.block_id}`).on("click", {
        askTimTitle: init_args.ask_tim_drawer_title,
        blockID: init_args.block_id,
        requestBody: init_args.request_body,
      }, function (event) {

        window.parent.postMessage(
          {
            type: "smoot-design::chat-open",
            payload: {
              chatId: event.data.blockID,
              askTimTitle: event.data.askTimTitle,
              apiUrl: init_args.learn_ai_api_url,
              initialMessages: INITIAL_MESSAGES,
              requestBody: event.data.requestBody,
            },
          },
          init_args.learning_mfe_base_url, // Ensure correct parent origin
        );

      });
    });
  }

  function AiChatAside(runtime, element, block_element, init_args) {
    return new AiChatAsideView(runtime, element, block_element, init_args);
  }

  window.AiChatAsideInit = AiChatAside;
})($);
