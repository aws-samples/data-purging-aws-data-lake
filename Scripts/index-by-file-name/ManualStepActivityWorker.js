'use strict';
console.log('Loading function');
const aws = require('aws-sdk');
const stepfunctions = new aws.StepFunctions();
const ses = new aws.SES();
exports.handler = (event, context, callback) => {
    
    var taskParams = {
        activityArn: 'arn:aws:states:us-east-1:297109802302:activity:ManualStep'
    };
    
    stepfunctions.getActivityTask(taskParams, function(err, data) {
        if (err) {
            console.log(err, err.stack);
            context.fail('An error occured while calling getActivityTask.');
        } else {
            if (data === null) {
                // No activities scheduled
                context.succeed('No activities received after 60 seconds.');
            } else {
                // Get approver email address from step function state input
                var input = JSON.parse(data.input);
                var emailParams = {
                    Destination: {
                        ToAddresses: [
                            input.approverEmailAddress
                            ]
                    },
                    Message: {
                        Subject: {
                            Data: 'Your Approval Needed to Proceed!',
                            Charset: 'UTF-8'
                        },
                        Body: {
                            Html: {
                                Data: 'Hi!<br /><br />' +
                                    'Please review <b>'+input.bucketPath + '</b> that includes the S3 Objects and database records which will get deleted as part of your purge request! <br /><br/>' +
                                    'Can you please ' +
                                    '<a href=\'https://u54xczly9k.execute-api.us-east-1.amazonaws.com/respond/succeed?taskToken=' + encodeURIComponent(data.taskToken) + '\'>Approve</a>' +
                                    ' OR ' +
                                    '<a href=\'https://u54xczly9k.execute-api.us-east-1.amazonaws.com/respond/fail?taskToken=' + encodeURIComponent(data.taskToken) + '\'>Reject</a>',
                                Charset: 'UTF-8'
                            }
                        }
                    },
                    Source: input.approverEmailAddress,
                    ReplyToAddresses: [
                            input.approverEmailAddress
                        ]
                };
                    
                ses.sendEmail(emailParams, function (err, data) {
                    if (err) {
                        console.log(err, err.stack);
                        context.fail('Internal Error: The email could not be sent.');
                    } else {
                        console.log(data);
                        context.succeed('The email was successfully sent.');
                    }
                });
            }
        }
    });
};