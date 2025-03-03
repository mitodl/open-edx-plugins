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
        blockUsageKey: init_args.block_usage_key,
        blockID: init_args.block_id,
        transcriptAssetID: init_args.transcript_asset_id
      }, function (event) {

        window.parent.postMessage(
          {
            type: "smoot-design::chat-open",
            payload: {
              chatId: event.data.blockID,
              askTimTitle: event.data.askTimTitle,
              apiUrl: init_args.learn_ai_api_url,
              initialMessages: INITIAL_MESSAGES,
              blockID: event.data.blockID,
              blockUsageKey: event.data.blockUsageKey,
              transcriptAssetID: event.data.transcriptAssetID,
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
