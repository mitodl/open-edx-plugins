(function($) {
    'use strict';

    function OpenLearningChatView(runtime, element) {
        // Sometimes the element is a jQuery object instead of a DOM object which leads to the broken chat form reference
        if (element instanceof jQuery){
            element = element[0]
        }
        const chatForm = element.querySelector("#ol-chat-form")
        chatForm.addEventListener("submit", function(event) {
            event.preventDefault();
            var studioRuntime = new window.StudioRuntime.v1();
            const enabledCheck = element.querySelector("#is-enabled-"+chatForm.dataset.blockId);

            // Get the handler URL
            const handlerUrl = studioRuntime.handlerUrl(element, 'update_chat_config');
            var dataToPost = {"is_enabled": enabledCheck.checked};

            $.ajax({
                url: handlerUrl,
                method: 'POST',
                data: JSON.stringify(dataToPost),
                contentType: 'application/json; charset=utf-8',
                success: function (response) {
                    alert("Saved successfully!");
                },
                error: function (xhr, status, error) {
                    alert("There was an error saving the details. Please try again");
                }
            });

        });
    }
    function initializeOLChat(runtime, element) {
        return new OpenLearningChatView(runtime, element);
    }

    window.OLChatInit = initializeOLChat;
}($));
