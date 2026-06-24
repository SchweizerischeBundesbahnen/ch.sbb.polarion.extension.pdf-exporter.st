#!groovy

// PR gating happens in GitHub Actions (.github/workflows/system-tests.yml) against Polarion in a
// Docker container, so Jenkins is not in the merge path. Here we only run the system tests on a
// schedule against a persistent Polarion instance.

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
        // Do not auto-build when the org-folder scan detects a new commit (BranchIndexingCause).
        // GitHub webhooks are not delivered to this Jenkins, so the org folder polls GitHub and
        // would otherwise trigger an indexing build on every push to main. That build skips the
        // stage below, fails on the empty JUnit report, and posts a misleading status to the
        // commit. This veto applies only to BranchIndexingCause; the nightly cron (TimerTrigger)
        // and manual runs (UserIdCause) are unaffected. PRs are gated by GitHub Actions instead.
        overrideIndexTriggers(false)
    }
    triggers {
        // Nightly run against the persistent Polarion instance; PRs are gated by GitHub Actions instead.
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
                lock resource: 'polarion-system-tests'  // Serialize across repos/branches — concurrent runs against the shared Polarion instance cause flaky results
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
                                uv run tox -e test -- --app_url ${POLARION_BASE_URL} --app_token ${AUTH_TOKEN}
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
