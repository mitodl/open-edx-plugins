(function ($) {
  // The AskTIM button that last opened the drawer. The drawer renders in the
  // parent MFE (cross-origin), so when it closes it can't focus our button
  // directly; it messages us back and we return focus to this trigger.
  var lastTrigger = null;
  // The drawer-closed listener is global, so bind it once across all blocks.
  var closeListenerBound = false;

  function AiChatAsideView(runtime, element, block_element, init_args) {
    $(function ($) {
      var mfeBaseUrl = init_args.learning_mfe_base_url;

      $(`#chat-button-${init_args.block_id}`).on(
        "click",
        {
          payload: init_args.drawer_payload,
        },
        function (event) {
          // Remember which button opened the drawer so focus can return here
          // when the drawer closes.
          lastTrigger = this;
          // Keyboard-fired click has detail === 0 (mouse >= 1); tell the drawer
          // so it rings the heading for keyboard opens only (it renders
          // cross-origin, so it can't infer this via :focus-visible).
          var nativeEvent = event.originalEvent || event;
          var viaKeyboard = nativeEvent.detail === 0;

          window.parent.postMessage(
            {
              type: "smoot-design::tutor-drawer-open",
              payload: event.data.payload,
              viaKeyboard: viaKeyboard,
            },
            mfeBaseUrl, // Ensure correct parent origin
          );
        },
      );

      // Bind once (not per block): when the drawer closes it posts back so we
      // can return keyboard focus to the button that opened it (WCAG 2.4.3).
      if (!closeListenerBound && mfeBaseUrl) {
        closeListenerBound = true;
        var mfeOrigin;
        try {
          mfeOrigin = new URL(mfeBaseUrl).origin;
        } catch (e) {
          mfeOrigin = mfeBaseUrl;
        }
        window.addEventListener("message", function (event) {
          if (event.origin !== mfeOrigin) {
            return;
          }
          if (!event.data || !lastTrigger) {
            return;
          }
          if (event.data.type === "smoot-design::tutor-drawer-closed") {
            // Drawer is gone: return focus, then forget the trigger.
            lastTrigger.focus();
            lastTrigger = null;
          }
        });
      }
    });
  }

  function AiChatAside(runtime, element, block_element, init_args) {
    return new AiChatAsideView(runtime, element, block_element, init_args);
  }

  window.AiChatAsideInit = AiChatAside;
})($);
