#!groovy

// PR gating now happens in GitHub Actions (.github/workflows/system-tests.yml) against
// Polarion in a Docker container, so Jenkins is no longer in the merge path. Here we only
// run system tests on a schedule against the real Polarion SUT and notify on failure.
def notifyOnFailure(String status) {
    String recipient = env.POLARION_NOTIFY_EMAIL
    if (recipient) {
        mail to: recipient,
             subject: "Polarion system tests ${status}: ${env.JOB_NAME} #${env.BUILD_NUMBER}",
             body: "Scheduled system tests against the Polarion SUT ${status}.\n\n${env.BUILD_URL}"
    } else {
        echo "System tests ${status}. Set the POLARION_NOTIFY_EMAIL env var to enable e-mail notifications. See ${env.BUILD_URL}"
    }
}

pipeline {
    agent {
        label 'polarion-testing-latest'
    }
    options {
        ansiColor('xterm')
        disableConcurrentBuilds()
        timestamps()
    }
    triggers {
        cron('H 2 * * *')  // Nightly run against the Polarion SUT; PRs are gated by GitHub Actions instead
    }
    stages {
        stage('System Tests') {
            when {
                // Scheduled or manual runs only — do not run per push/PR (that is handled by GitHub Actions)
                anyOf {
                    triggeredBy 'TimerTrigger'
                    triggeredBy cause: 'UserIdCause'
                }
            }
            options {
                lock resource: 'polarion-system-tests'  // Serialize across repos/branches — concurrent runs against the shared Polarion instance cause flaky visual diffs
            }
            stages {
                stage('Install uv') {
                    steps {
                        sh "curl -LsSf https://astral.sh/uv/install.sh | sh"
                        sh "export PATH=\"\$HOME/.local/bin:\$PATH\" && uv --version"
                    }
                }
                stage('Install Python requirements') {
                    steps {
                        sh '''
                            export PATH="$HOME/.local/bin:$PATH"
                            uv sync --frozen
                        '''
                    }
                }
                stage('Run system tests with tox') {
                    steps {
                        withCredentials([
                            string(credentialsId: 'POLARION-system-test-url', variable: 'POLARION_BASE_URL'),
                            string(credentialsId: 'POLARION-system-test-token', variable: 'AUTH_TOKEN')
                        ]) {
                            sh '''
                                export PATH="$HOME/.local/bin:$PATH"
                                uv run tox -- --app_url ${POLARION_BASE_URL} --app_token ${AUTH_TOKEN}
                            '''
                        }
                    }
                }
            }
        }
    }
    post {
        always {
            junit skipPublishingChecks: true, testResults: '**/TEST-*.xml'
            archiveArtifacts artifacts: '**/test-data/output/**', allowEmptyArchive: true
        }
        failure {
            notifyOnFailure('FAILED')
        }
        unstable {
            notifyOnFailure('UNSTABLE')
        }
    }
}
