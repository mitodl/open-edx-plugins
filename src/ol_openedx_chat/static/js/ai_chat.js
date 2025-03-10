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
        blockId: init_args.block_id,
        edxModuleId: init_args.edx_module_id,
        requestBody: init_args.request_body,
        apiURL: init_args.chat_api_url
      }, function (event) {

        window.parent.postMessage(
          {
            type: "smoot-design::chat-open",
            payload: {
              chatId: event.data.blockId,
              edxModuleId: event.data.edxModuleId,
              askTimTitle: event.data.askTimTitle,
              apiUrl: event.data.apiURL,
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
