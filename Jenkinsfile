#!groovy

// PR gating now happens in GitHub Actions (.github/workflows/system-tests.yml) against
// Polarion in a Docker container, so Jenkins is no longer in the merge path. Here we only
// run system tests on a schedule against the real Polarion SUT. Build status is reported to
// GitHub automatically and visible in the Jenkins UI; we just log the outcome here.
def notifyOnFailure(String status) {
    echo "Polarion system tests ${status}. See ${env.BUILD_URL}"
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
        // Nightly run against the Polarion SUT; PRs are gated by GitHub Actions instead.
        // Timed to start after the scheduled nightly environment auto-update has completed.
        cron('H 2 * * *')
    }
    stages {
        stage('System Tests') {
            when {
                // Run only on the main branch and only for scheduled or manual builds. This is a
                // multibranch job, so without the branch guard every feature/PR branch would also
                // run these tests — those are gated by GitHub Actions instead.
                allOf {
                    branch 'main'
                    anyOf {
                        triggeredBy 'TimerTrigger'
                        triggeredBy cause: 'UserIdCause'
                    }
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
