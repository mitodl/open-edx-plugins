(function ($) {
  function AiChatAsideView(runtime, element, block_element, init_args) {

    function emitTrackingEvent(eventName, eventData) {
        $.ajax({
            type: 'POST',
            url: runtime.handlerUrl(element, 'track_user_events'),
            data: JSON.stringify({
              event_name: eventName,
              event_data: eventData
            }),
            dataType: 'json',
            contentType: 'application/json; charset=utf-8'
        });
    }

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

        emitTrackingEvent('ol_openedx_chat.chat_drawer_opened', {
          block_usage_key: event.data.payload.chat.requestBody.edx_module_id,
          user_id: event.data.payload.chat.userId,
        });

      });
    });
  }

  function AiChatAside(runtime, element, block_element, init_args) {
    return new AiChatAsideView(runtime, element, block_element, init_args);
  }

  window.AiChatAsideInit = AiChatAside;
})($);
