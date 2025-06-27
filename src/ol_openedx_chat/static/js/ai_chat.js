(function ($) {
  function AiChatAsideView(runtime, element, block_element, init_args) {
    $(function ($) {

      $(`#chat-button-${init_args.block_id}`).on("click", {
        payload: init_args.drawer_payload,
      }, function (event) {

        window.parent.postMessage(
          {
            type: "smoot-design::tutor-drawer-open",
            payload: event.data.payload
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
