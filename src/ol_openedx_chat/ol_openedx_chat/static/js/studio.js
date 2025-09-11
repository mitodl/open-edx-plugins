(function($) {
    'use strict';

    function OpenLearningChatView(runtime, element) {
        var $element = $(element);
        var AIChatConfigUpdateInProgress = false;
        // we need studio runtime to get handler capable of saving xblock data
        var studioRuntime = new window.StudioRuntime.v1();

        $($element).find('.enabled-check').change(function(e) {
            var dataToPost = {"is_enabled": this.checked};
            if (!AIChatConfigUpdateInProgress) {
                AIChatConfigUpdateInProgress = true;

                e.preventDefault();
                runtime.notify('save', {
                    state: 'start',
                    element: element,
                    message: gettext('Updating Chat Config')
                });

                $.ajax({
                    type: 'POST',
                    url: studioRuntime.handlerUrl(element, 'update_chat_config'),
                    data: JSON.stringify(dataToPost),
                    dataType: 'json',
                    contentType: 'application/json; charset=utf-8'
                }).done(function () {
                    try {
                        window.parent.postMessage({
                            type: 'saveEditedXBlockData',
                            message: 'Sends a message when the xblock data is saved',
                            payload: {}
                        }, document.referrer);
                    } catch (e) {
                        console.error(e);
                    }
                }).always(function() {
                    runtime.notify('save', {
                        state: 'end',
                        element: element
                    });
                    AIChatConfigUpdateInProgress = false;
                });

            }
        });
    }

    function initializeOLChat(runtime, element) {
        return new OpenLearningChatView(runtime, element);
    }

    window.OLChatInit = initializeOLChat;
}($));
